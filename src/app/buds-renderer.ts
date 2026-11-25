// The supplied GLB stores each rigid part in its own root group. The lid pivots
// around its hinge and the right earbud rotates around its original local origin.
type Vec3 = [number, number, number];
interface Material { baseColorFactor: number[]; roughnessFactor: number; metallicFactor: number }
interface Model {
  scenes: { nodes: number[] }[];
  nodes: { children: number[]; mesh: number; rotation: number[]; extras: { group: string } }[];
  meshes: { primitives: { attributes: { POSITION: number; NORMAL: number }; indices: number; material: number }[] }[];
  bufferViews: { target: number; byteOffset?: number; byteLength: number }[];
  accessors: { bufferView: number; componentType: number; count: number }[];
  materials: { pbrMetallicRoughness: Material }[];
}
export interface Pose {
  open: number; lift: number;
}
export const presets: Pose[] = [
  { open: 0, lift: 0 },
  { open: 103, lift: 0 },
  { open: 108, lift: 1 }
];
const vertex = `#version 300 es
layout(location=0) in vec3 vertex;
layout(location=1) in vec3 normal;
uniform vec3 pivot,position,axis,target,right,up,eye;
uniform float angle,aspect,zoom;
out vec3 N;
out float elevation;
void main() {
  float c=cos(angle),s=sin(angle);
  mat3 r=c*mat3(1.)+(1.-c)*outerProduct(axis,axis)+s*mat3(0.,axis.z,-axis.y,-axis.z,0.,axis.x,axis.y,-axis.x,0.);
  N=r*normal;
  vec3 world=r*(vertex*1000.-pivot)+pivot+position;
  elevation=world.y;
  vec3 p=world-target;
  gl_Position=vec4(dot(p,right)/zoom/aspect,dot(p,up)/zoom,-dot(p,eye)/180.,1.);
}`;
const fragment = `#version 300 es
precision highp float;
in vec3 N;
in float elevation;
uniform vec3 eye,albedo;
uniform float rough,metal;
out vec4 color;
float panel(vec3 ray, vec3 dir,vec3 across,vec2 size) {
  dir=normalize(dir); across=normalize(across-dot(across,dir)*dir);
  float facing=dot(ray,dir);
  if(facing<0.001)return 0.;
  vec2 edge=abs(vec2(dot(ray,across),dot(ray,cross(dir,across)))/facing)-size;
  return 1.-smoothstep(-rough,rough,max(edge.x,edge.y));
}
void main() {
  vec3 n=normalize(N)*(gl_FrontFacing?1.:-1.);
  vec3 ray=reflect(-eye,n);
  float key=panel(ray,vec3(-.8,1.1,.8),vec3(0,1,0),vec2(.72,.32));
  float rim=panel(ray,vec3(.9,.45,-.5),vec3(0,1,0),vec2(.95,.25));
  float top=panel(ray,vec3(.35,1.,.45),vec3(1,0,0),vec2(.95,.15));
  float fres=.046+.48*pow(1.-max(dot(n,eye),0.),3.);
  vec3 lights=key*vec3(2.1,2.65,3.15)+rim*vec3(.24,1.3,3.8)+top*vec3(.68,.90,1.22);
  vec3 diffuse=albedo*(vec3(.065,.08,.12)+vec3(.53,.64,.78)*max(dot(n,normalize(vec3(-.7,1,.65))),0.));
  vec3 linear=diffuse+mix(vec3(fres),albedo,metal)*(lights+vec3(.045,.075,.14));
  float rimFacing=smoothstep(-.45,.75,dot(n,normalize(vec3(.86,.45,-.33))));
  linear+=mix(vec3(.013,.025,.049),vec3(.085,.23,.47),rimFacing)*pow(1.-max(dot(n,eye),0.),3.);
  linear*=mix(.39,1.,smoothstep(.15,9.,elevation));
  color=vec4(pow(linear,vec3(1./2.2)),1.);
}`;
export async function createRenderer(canvas: HTMLCanvasElement, signal: AbortSignal) {
  const gl = canvas.getContext('webgl2', { alpha: true, antialias: true });
  if (!gl) throw new Error('WebGL2 unavailable');
  const response = await fetch(new URL('media/redmi-buds-6-play.glb', document.baseURI), {signal});
  if (!response.ok) throw new Error('Model unavailable');
  const data = await response.arrayBuffer();
  signal.throwIfAborted();
  const jsonLength = new DataView(data).getUint32(12, true);
  const doc: Model = JSON.parse(new TextDecoder().decode(new Uint8Array(data, 20, jsonLength)));
  const program = gl.createProgram()!;
  for (const [type, src] of [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? 'Shader');
    gl.attachShader(program, shader);
    gl.deleteShader(shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Shader linking failed');
  gl.useProgram(program);
  const uniform = Object.fromEntries('pivot position axis target right up eye angle aspect zoom albedo rough metal'.split(' ').map(key => [key, gl.getUniformLocation(program,key)]));
  const buffers = doc.bufferViews.map(view => {
    const buffer = gl.createBuffer();
    gl.bindBuffer(view.target,buffer);
    gl.bufferData(view.target,new Uint8Array(data,28+jsonLength+(view.byteOffset ?? 0),view.byteLength),gl.STATIC_DRAW);
    return buffer;
  });
  const parts = doc.scenes[0].nodes.flatMap(index => {
    const root = doc.nodes[index];
    return root.children.map(child => {
      const primitive = doc.meshes[doc.nodes[child].mesh].primitives[0];
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      [primitive.attributes.POSITION,primitive.attributes.NORMAL].forEach((index, location) => {
        gl.bindBuffer(gl.ARRAY_BUFFER,buffers[doc.accessors[index].bufferView]);
        gl.vertexAttribPointer(location,3,gl.FLOAT,false,0,0);
        gl.enableVertexAttribArray(location);
      });
      const indices = doc.accessors[primitive.indices];
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,buffers[indices.bufferView]);
      return { group: root.extras.group, vao, indices, material: doc.materials[primitive.material].pbrMetallicRoughness };
    });
  });
  const rotation = doc.nodes.find(node => node.extras?.group === 'right')!.rotation;
  const halfAngle = Math.acos(rotation[3]);
  const liftAxis = rotation.slice(0,3).map(value => value / Math.sin(halfAngle));
  gl.enable(gl.DEPTH_TEST);
  gl.clearColor(0,0,0,0);
  return {
    draw(p: Pose) {
      const dpr = Math.min(devicePixelRatio,2);
      const width = Math.max(1,Math.round(canvas.clientWidth*dpr));
      const height = Math.max(1,Math.round(canvas.clientHeight*dpr));
      if (width !== canvas.width || height !== canvas.height) { canvas.width = width; canvas.height = height; }
      gl.viewport(0,0,width,height);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      const sy = Math.sin(-.40), cy = Math.cos(-.40), sp = Math.sin(.36), cp = Math.cos(.36);
      gl.uniform3fv(uniform['eye'],[sy*cp,sp,cy*cp]);
      gl.uniform3fv(uniform['right'],[cy,0,-sy]);
      gl.uniform3fv(uniform['up'],[-sy*sp,cp,-cy*sp]);
      gl.uniform3fv(uniform['target'],[0,34,-2]);
      gl.uniform1f(uniform['aspect'],width/height);
      gl.uniform1f(uniform['zoom'],50*Math.max(1,height/width));
      for (const part of parts) {
        let position: Vec3 = [0,0,0], angle = 0;
        const rightBud = part.group === 'right';
        if (part.group === 'lid') { position = [0,18.2,-25.4]; angle = -p.open*Math.PI/180; }
        if (rightBud) { position = [10+23*p.lift,15+47*p.lift,8.7+3*p.lift]; angle = 2*halfAngle*p.lift; }
        const leftBud = part.group === 'left';
        if (leftBud) {
          position = [-21*p.lift,40*p.lift,7*p.lift];
          angle = -1.18*p.lift;
        }
        gl.uniform3fv(uniform['pivot'],leftBud ? [-10,15,8.7] : [0,0,0]);
        gl.uniform3fv(uniform['position'],position);
        gl.uniform3fv(uniform['axis'],rightBud ? liftAxis : leftBud ? [0,.8,.6] : [1,0,0]);
        gl.uniform1f(uniform['angle'],angle);
        gl.uniform3fv(uniform['albedo'],part.material.baseColorFactor.slice(0,3));
        gl.uniform1f(uniform['rough'],part.material.roughnessFactor);
        gl.uniform1f(uniform['metal'],part.material.metallicFactor);
        gl.bindVertexArray(part.vao);
        gl.drawElements(gl.TRIANGLES,part.indices.count,part.indices.componentType,0);
      }
    },
    destroy() {
      parts.forEach(part => gl.deleteVertexArray(part.vao));
      buffers.forEach(buffer => gl.deleteBuffer(buffer));
      gl.deleteProgram(program);
    }
  };
}

