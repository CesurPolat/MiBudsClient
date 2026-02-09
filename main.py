import flet as ft
import threading
import time
from controller import BTController

def main(page: ft.Page):
    page.title = "Redmi Buds 6 Play"
    page.bgcolor = "#000000"
    page.padding = 20
    
    page.window_width = 400
    page.window_height = 700
    page.window_resizable = False
    page.window_maximizable = False
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    def format_bat(val):
        if val == 0xFF: return "---", "grey"
        is_charging = val >= 128
        actual_val = val - 128 if is_charging else val
        if actual_val > 100: return "---", "grey"
        text = f"%{actual_val}"
        if is_charging:
            return f"⚡ {text}", "#4CAF50"
        return text, "#2196F3"

    def ui_call(fn):
        call_from_thread = getattr(page, "call_from_thread", None)
        if callable(call_from_thread):
            call_from_thread(fn)
        else:
            fn()

    def battery_info(label):
        return ft.Column([
            ft.Text(label, color="grey", size=12),
            ft.Text("--", color="white", size=16, weight="bold")
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    left_info = battery_info("LEFT")
    left_val = left_info.controls[1]
    right_info = battery_info("RIGHT")
    right_val = right_info.controls[1]
    case_info = battery_info("CASE")
    case_val = case_info.controls[1]

    def setting_item(icon, color, title, on_click=None):
        return ft.ListTile(
            leading=ft.Container(
                content=ft.Icon(icon, color="white"),
                bgcolor=color,
                border_radius=10,
                width=40, height=40
            ),
            title=ft.Text(title, color="white", weight="medium"),
            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color="grey"),
            on_click=on_click
        )

    status_text = ft.Text("Status: Starting...", color="grey", size=12)

    def on_pubsub_message(message):
        if not isinstance(message, dict):
            return
        msg_type = message.get("type")
        if msg_type == "status":
            status_text.value = f"Status: {message.get('text', '')}"
            status_text.color = message.get("color", "white")
            page.update()
        elif msg_type == "battery":
            l = message.get("left", 0xFF)
            r = message.get("right", 0xFF)
            c = message.get("case", 0xFF)
            l_text, l_color = format_bat(l)
            r_text, r_color = format_bat(r)
            c_text, c_color = format_bat(c)
            left_val.value = l_text
            left_val.color = l_color
            right_val.value = r_text
            right_val.color = r_color
            case_val.value = c_text
            case_val.color = c_color
            page.update()

    page.pubsub.subscribe(on_pubsub_message)

    def update_battery_ui(l, r, c):
        page.pubsub.send_all({"type": "battery", "left": l, "right": r, "case": c})

    def update_status(text, color="white"):
        page.pubsub.send_all({"type": "status", "text": text, "color": color})

    def on_check_battery_delayed():
        time.sleep(1)
        controller.request_battery()

    controller = BTController(
        status_callback=update_status,
        battery_callback=update_battery_ui,
        check_battery_callback=lambda: threading.Thread(target=on_check_battery_delayed, daemon=True).start()
    )

    settings_card = ft.Container(
        content=ft.Column([
                setting_item(ft.Icons.SPEED, "blue700", "Low Latency Mode (On)", 
                         on_click=lambda _: controller.send_command("low")),
            ft.Divider(color="white10", thickness=0.5),
                setting_item(ft.Icons.TIMER, "blue800", "Standard Mode (Off)", 
                         on_click=lambda _: controller.send_command("std")),
            ft.Divider(color="white10", thickness=0.5),
                setting_item(ft.Icons.REFRESH, "grey700", "Check Battery", 
                         on_click=lambda _: controller.request_battery()),
        ], spacing=0),
        bgcolor="#1A1A1A",
        border_radius=20,
        padding=10
    )

    page.add(
        ft.Text("Redmi Buds 6 Play", size=24, weight="bold", color="white"),
        ft.Container(height=20),
        ft.Image(src="MiBuds6Play.jpg", width=200, height=200, error_content=ft.Icon(ft.Icons.HEADSET, size=100, color="white10")),
        ft.Container(height=20),
        ft.Row([left_info, right_info, case_info], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        ft.Container(height=20),
        settings_card,
        ft.Container(expand=True),
        status_text
    )

    threading.Thread(target=controller.listen, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=main)
