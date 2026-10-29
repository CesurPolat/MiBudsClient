[English](../../README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · **Español** · [Français](README.fr.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md)

<div align="center">

<img src="../../assets/icon.png" alt="Icono de MiBudsClient" width="88">

# MiBudsClient

**Tus auriculares Xiaomi y Redmi, en el escritorio.**

Batería, baja latencia, perfiles de sonido y controles táctiles en un solo lugar.<br>
Creado con Python y Flet para Windows y Linux.

[**Descargar**](https://github.com/CesurPolat/MiBudsClient/releases) · [Primeros pasos](#primeros-pasos) · [Ejecutar desde el código fuente](#ejecutar-desde-el-código-fuente) · [Informar de un problema](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="Vista previa de la interfaz de MiBudsClient" width="720">

</div>

## Funciones

| Función | Qué ofrece |
| --- | --- |
| Batería | Niveles separados de ambos auriculares y del estuche, indicadores de carga y actualización manual. |
| Baja latencia | Desactivar, activar o cambiar automáticamente el modo de juego según la aplicación activa. |
| Perfiles de sonido | Leer y cambiar los ajustes de EQ que ofrece el dispositivo. |
| Controles táctiles | Editar las asignaciones izquierda y derecha para uno, dos o tres toques y pulsación prolongada. |
| Notificaciones | Conexión, desconexión y cambios en el estuche con batería e imagen cuando estén disponibles. |
| Bandeja del sistema | Funcionar en segundo plano, restaurar la ventana y cambiar el modo de latencia. |
| Comodidad | Conexión automática, inicio con el sistema, preferencias guardadas y comprobación de actualizaciones. |
| Idiomas | 27 variantes regionales en 24 idiomas, cambio inmediato y disposición de derecha a izquierda para árabe. |

## Compatibilidad

**El dispositivo compatible es Redmi Buds 6 Play.** El catálogo Xiaomi/Redmi incluye nombres, imágenes y capacidades de otros modelos. Una entrada en el catálogo no demuestra compatibilidad con su control.

Windows y Linux usan detección Bluetooth específica para cada plataforma. En Linux, la bandeja y las notificaciones dependen del escritorio. La detección automática de pantalla completa usa X11 y no está disponible en Wayland. La validación de hardware e interfaz en Linux sigue pendiente.

MiBudsClient es un proyecto comunitario independiente sin afiliación con Xiaomi.

## Primeros pasos

1. Empareja y conecta los auriculares en los ajustes Bluetooth del ordenador.
2. Descarga un paquete para tu plataforma desde [Releases](https://github.com/CesurPolat/MiBudsClient/releases) o [ejecuta desde el código fuente](#ejecutar-desde-el-código-fuente).
3. Abre MiBudsClient. Busca dispositivos conectados del catálogo e intenta establecer automáticamente una conexión de control Bluetooth.
4. Comprueba las tarjetas de batería y elige el modo de latencia. Abre **Ajustes** para gestos, EQ, inicio e idioma.

El sistema operativo gestiona el emparejamiento. La aplicación necesita una conexión Bluetooth existente. Solo se ejecuta una instancia; abrirla de nuevo muestra la ventana existente. Usa la opción de salir de la bandeja para cerrarla por completo.

## Uso

### Baja latencia

- **Desactivado:** Modo estándar.
- **Activado:** Baja latencia manual.
- **Automático:** Activa la baja latencia con aplicaciones a pantalla completa. **Incluir** la activa también sin pantalla completa; **Excluir** omite esa aplicación.

**Esperar hasta que se cierre la aplicación** mantiene la baja latencia hasta que termine la aplicación detectada. Las reglas se guardan por separado para Windows y Linux.

### Ecualizador

Abre **Ajustes → Ecualizador** para leer el perfil y los ajustes disponibles. Los cambios requieren confirmación del dispositivo y una nueva lectura de verificación.

El editor personalizado aparece solo con datos de bandas válidos. Al soltar un deslizador se envía una vista previa; guardar almacena la curva y restablecer solicita una curva plana. Cierra y vuelve a abrir la sección tras un error o para recargar los datos.

El cambio de perfiles se verificó con Redmi Buds 6 Play el **2026-10-27**. El dispositivo probado no devolvió bandas personalizadas; la vista previa, el guardado y el restablecimiento personalizados no están verificados en hardware. [Notas técnicas de EQ](../equalizer.md) (en inglés).

### Gestos táctiles

En **Ajustes → Gestos**, carga las asignaciones. Cada gesto tiene selectores izquierdo y derecho; las opciones proceden de la entrada exacta del modelo. Los cambios se envían inmediatamente y solo se muestran como guardados después de leerlos de nuevo. Se almacenan en los auriculares. No se incluye editar ciclos ANC.

La lectura y reescritura de valores existentes se verificaron el **2026-10-26**. Asignar otra función y activarla físicamente aún requieren verificación manual.

### Notificaciones e idioma

Los avisos incluyen batería cuando está disponible. Introducir o retirar los auriculares se deduce del indicador de carga; no se consulta un sensor independiente de estuche o colocación en el oído. Al desconectar se usan los últimos valores conocidos.

Pulsar una notificación restaura la ventana. En Linux, el servidor debe admitir acciones predeterminadas. Se suprimen los sonidos de notificación del sistema. La aplicación reproduce sus propias melodías al cambiar el estado de carga y una vez en la primera conexión correcta de cada sesión.

En **Ajustes → Idioma**, elige el idioma del sistema o uno específico. La preferencia se guarda y se aplica inmediatamente a la interfaz, bandeja y futuras notificaciones. Si el idioma del sistema no es compatible, se usa inglés.

Idiomas: árabe, chino (simplificado, Taiwán, Hong Kong), neerlandés, inglés, estonio, finés, francés, alemán, hindi, húngaro, indonesio, italiano, japonés, coreano, malayo, polaco, portugués (Brasil y Portugal), ruso, español, sueco, tailandés, turco, ucraniano y vietnamita.

## Ejecutar desde el código fuente

Necesitas Python con `venv` y `pip`, un adaptador Bluetooth y los auriculares conectados mediante el sistema operativo.

```sh
git clone https://github.com/CesurPolat/MiBudsClient.git
cd MiBudsClient
```

**Windows — PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

**Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux requiere `bluetoothctl` de BlueZ para detectar dispositivos y PyGObject (`gi`) con AppIndicator3 o GTK para la bandeja. La detección X11 también necesita `xprop`, `xwininfo` y `xrandr`. Son dependencias del sistema; `requirements.txt` solo instala paquetes Python.

## Solución de problemas

| Problema | Qué comprobar |
| --- | --- |
| No se encuentran auriculares | Activa Bluetooth, confirma la conexión en los ajustes del sistema y vuelve a intentarlo. |
| Tiempo de espera agotado | Mantén los auriculares encendidos y cerca. Desactiva Bluetooth del ordenador, espera 10 segundos y actívalo. Si hace falta, coloca ambos en el estuche, cierra la tapa 5 segundos, sácalos y vuelve a intentar. |
| Falta la batería | Usa la comprobación de batería tras conectar. Los datos ausentes se consideran desconocidos. |
| Error de gestos o EQ | Cierra y abre la sección para leer otra vez el estado del dispositivo. |
| No aparece EQ personalizado | Requiere bandas válidas; el dispositivo probado no las proporcionó. Los perfiles pueden seguir disponibles. |
| El modo automático no funciona en Linux | Comprueba X11 y las herramientas indicadas. No hay detección en Wayland. |
| Pulsar la notificación en Linux no funciona | Comprueba las acciones predeterminadas del servidor o abre desde la bandeja. |

Al [informar de un problema](https://github.com/CesurPolat/MiBudsClient/issues), incluye versión, sistema operativo y sesión de escritorio, modelo, pasos para reproducirlo y detalles del error.

## Desarrollo

`main.py` inicia y conecta los componentes. `controllers/` contiene Bluetooth, estado del dispositivo, latencia y ajustes; `ui/`, la interfaz Flet, bandeja y notificaciones; `utils/`, utilidades de plataforma. Los recursos están en `assets/`, las pruebas en `tests/` y la documentación en `docs/`.

Ejecuta desde la raíz del repositorio en tu entorno de desarrollo:

```sh
python -m unittest discover -s tests
```

Los cambios de protocolo y constantes también deben probarse con Redmi Buds 6 Play reales. Las pruebas sintéticas no demuestran compatibilidad. Lee [AGENTS.md](../../AGENTS.md) antes de cambiar el comportamiento del dispositivo o el empaquetado.

Las traducciones están en `assets/locales/`. Consulta la [guía de localización](../localization.md) (en inglés) sobre claves, parámetros y recursos Xiaomi. Actualiza `docs/readme/` junto con la versión inglesa al cambiar funciones o instalación.

### Crear un ejecutable

Con la CLI de Flet disponible en el entorno activo, ejecuta en la plataforma de destino:

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

Mantén los recursos de interfaz en `assets/` para incluirlos en el paquete. Antes de publicar, prueba con los auriculares y abre el ejecutable dos veces: la segunda instancia debe enfocar la ventana existente y cerrarse silenciosamente.

## Licencia

MiBudsClient se distribuye bajo la [Licencia Pública General de GNU v3.0](../../LICENSE).
