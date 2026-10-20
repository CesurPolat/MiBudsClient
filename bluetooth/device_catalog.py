"""User-supplied identity metadata; recognition does not imply protocol support."""


# Original Chinese labels keyed by internal code, retained for future zh locales.
# Current identity results continue to use the English product names below.
PRODUCT_NAMES_ZH = {
    "K73": "Xiaomi 真无线降噪耳机 3 Pro",
    "K75": "Xiaomi 真无线降噪耳机 3",
    "O73": "Xiaomi 骨传导耳机 2",
    "O74": "Xiaomi 开放式耳机 Pro",
    "Q74u": "Xiaomi 耳夹式耳机",
}


# SDK constants without a confirmed VID; excluded from identity lookup.
# None means the source did not supply a PID either.
SDK_PIDS_WITHOUT_VID = {
    "AI2000": 8452,
    "ANBEI": 13503,
    "AIR2S": 20506,
    "AIR2PRO": 20508,
    "AIR2Pokemon": None,
}


# (internal code, decimal PIDs, product family when supplied).
# Names shared by a PID remain ambiguous rather than selecting one product.
_XIAOMI_PRODUCTS = (
    ("J77S", (20505, 20534), None),
    ("K73", (20517, 20525), "Xiaomi Buds 3 Pro"),
    ("K73a", (20525,), "Xiaomi Buds 3T Pro"),
    ("K75", (20518, 20523), "Xiaomi Buds 3"),
    ("K75sStarWars", (20570,), None),
    ("L71", (20533, 20539), "Xiaomi Buds 4 Pro"),
    ("L77", (20532, 20535, 20536), "Redmi Buds 4"),
    ("L77s", (20573,), None),
    ("M75A", (20548, 20549), "Xiaomi Buds 4"),
    ("M79A", (20575, 20576, 20577, 20578, 20585), "Redmi Buds 4 Active"),# / Redmi Buds 5A / POCO Pods
    ("M79I", (20622,), None),
    ("N74A", (20607, 20608), "Xiaomi OpenWear Stereo"),
    ("N75", (20609, 20610), "Xiaomi Buds 5"),
    ("N76", (20588, 20589), "Redmi Buds 5 Pro"),
    ("N76G", (20591,), "Redmi Buds 5 Pro (Gaming Edition)"),
    ("N76GIP", (20590,), None),
    ("N77", (20586, 20597, 20615), "Redmi Buds 5"),
    ("N77Ip", (20587,), None),
    ("N77S", (20629,), "Redmi Buds 6S"),
    ("N79", (20616, 20617), "Redmi Buds 6 Active"),#/ Xiaomi Air4 SE
    ("N79A", (20618, 20619, 20620, 20621), "Redmi Buds 6 Lite"),# / Redmi Buds 5C / POCO Buds X1
    ("N79B", (20634, 20635), "Redmi Buds 6 Play"),#/ REDMI Buds SE
    ("N79S", (20636,), None),
    ("O70C", (20720, 20731), "REDMI Headphones Neo"),
    ("O71", (20651, 20652, 20653, 20660), "Xiaomi Buds 5 Pro"),
    ("O71BT", (20653, 20660), "Xiaomi Buds 5 Pro (Bluetooth)"),
    ("O71Wifi", (20651, 20652), "Xiaomi Buds 5 Pro (Wi-Fi)"),
    ("O73", (20661,), "Xiaomi Bone Conduction Earphones 2"),
    ("O74", (20664, 20695), "Xiaomi OpenWear Stereo Pro"),
    ("O76", (20637, 20638), "REDMI Buds 6 Pro"),
    ("O76G", (20655,), "REDMI Buds 6 Pro (Gaming Edition)"),
    ("O77", (20639, 20640, 20647), "Redmi Buds 6"),
    ("O77S", (20665,), "REDMI Buds 7S"),
    ("P75", (20714, 20715), "Xiaomi Buds 6"),
    ("P76", (20707, 20709), "REDMI Buds 8 Pro"),
    ("P76Bose", (20724,), None),
    ("P79", (20705, 20706), "REDMI Buds 8 Active"),
    ("Q74u", (20699, 20700), "Xiaomi OpenWear Stereo"),
)

# (internal code, decimal VID, decimal PIDs, product family when supplied).
_OTHER_PRODUCTS = (
    ("L76", 23117, (59918, 59919, 59920), "Redmi Buds 4 Pro"),
    ("K76", 23117, (59907,), "Redmi AirDots 3 Pro"),#/ POCO Buds Pro Genshin Impact Edition
    ("NZBT01", 23117, (44033,), None),
    ("B508", 23117, (47618,), None),
    ("B608", 23117, (47619,), None),
    ("TW100", 23117, (59905,), None),
    ("TW101", 23117, (59906,), None),
    ("WBS02", 23117, (47620,), None),
    ("S18", 10007, (13500,), None),
    ("K71", 1, (0,), None),
)


def _build_catalog():
    names = {}
    codes = {}
    products = (
        *((code, 0x2717, pids, family) for code, pids, family in _XIAOMI_PRODUCTS),
        *_OTHER_PRODUCTS,
    )
    for code, vid, pids, family in products:
        for pid in pids:
            key = (vid, pid)
            code_list = codes.setdefault(key, [])
            if code not in code_list:
                code_list.append(code)
            if family:
                name_list = names.setdefault(key, [])
                if family not in name_list:
                    name_list.append(family)
    return (
        {key: " / ".join(values) for key, values in names.items()},
        {key: tuple(values) for key, values in codes.items()},
    )


DEVICE_MODEL_NAMES, DEVICE_MODEL_CODES = _build_catalog()
