// Read the focused window once; do not change KWin settings or window state.
// output_result is supplied by kdotool's kwinscript command.
var window = workspace.activeWindow;
if (typeof workspace.activeWindow === "undefined")
    throw new Error("MiBudsClient requires the Plasma 6 KWin window API");
var state = {available: true, fullscreen: false, app_id: "", pid: 0};
if (window && !window.minimized && !window.desktopWindow && !window.dock) {
    if (typeof window.fullScreen !== "boolean")
        throw new Error("KWin fullscreen state is unavailable");
    state.fullscreen = window.fullScreen;
    state.app_id = String(window.resourceClass || window.desktopFileName || "");
    state.pid = Number(window.pid) || 0;
}
output_result(JSON.stringify(state));
