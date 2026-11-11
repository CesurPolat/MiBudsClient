import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const INTERFACE = `<node>
    <interface name="org.mibuds.Fullscreen">
        <method name="GetState">
            <arg name="state" type="s" direction="out"/>
        </method>
    </interface>
</node>`;

export default class FullscreenBridge extends Extension {
    enable() {
        this._bridge = Gio.DBusExportedObject.wrapJSObject(INTERFACE, this);
        this._bridge.export(Gio.DBus.session, '/org/mibuds/Fullscreen');
    }

    disable() {
        this._bridge?.unexport();
        this._bridge = null;
    }

    GetState() {
        const state = {
            version: 1, available: true, fullscreen: false, app_id: '', pid: 0,
        };
        try {
            // A game behind the lock screen or overview is not foreground.
            if (Main.sessionMode.isLocked || Main.overview.visible)
                return JSON.stringify(state);
            const window = global.display.get_focus_window();
            if (window && !window.minimized) {
                state.fullscreen = window.is_fullscreen();
                state.app_id = window.get_wm_class() || window.get_gtk_application_id()
                    || window.get_sandboxed_app_id() || '';
                state.pid = window.get_pid();
            }
        } catch (error) {
            state.available = false;
        }
        return JSON.stringify(state);
    }
}
