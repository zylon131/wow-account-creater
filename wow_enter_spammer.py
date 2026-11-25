"""
╔══════════════════════════════════════════════════════════════╗
║  魔兽世界角色创建后台自动回车脚本（国服适配版）              ║
║  — 阵营锁定抢号助手（随机化间隔，模拟人工操作）              ║
║                                                              ║
║  即使窗口在后台，也会向魔兽世界窗口发送随机间隔的回车键。    ║
║  快捷键: F6 = 开始/暂停 | F7 = 退出                          ║
╚══════════════════════════════════════════════════════════════╝
"""

import ctypes
import ctypes.wintypes
import random
import sys
import threading
import time
import keyboard

# ═══════════════════════════════════════════════════════════
# Win32 常量与 API
# ═══════════════════════════════════════════════════════════
WM_KEYDOWN = 0x0100
WM_KEYUP   = 0x0101
VK_RETURN  = 0x0D  # 回车键

user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
IsWindow = user32.IsWindow
PostMessageW = user32.PostMessageW

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

# ═══════════════════════════════════════════════════════════
# 默认配置（支持通过命令行参数覆盖）
# ═══════════════════════════════════════════════════════════
MIN_DELAY_MS = 650    # 每次按键最小间隔（毫秒）
MAX_DELAY_MS = 1850   # 每次按键最大间隔（毫秒）
MIN_HOLD_MS  = 35     # 按键按下到抬起的最短时长（毫秒）
MAX_HOLD_MS  = 95     # 按键按下到抬起的最长时长（毫秒）
PAUSE_CHANCE = 0.06   # 每次循环有 6% 概率触发短暂“人工停顿”（2~4.5秒）

HOTKEY_TOGGLE = "f6"  # 开始/暂停热键
HOTKEY_EXIT = "f7"    # 退出热键

# 魔兽世界窗口标题关键词（已适配国服与国际服）
WOW_TITLES = [
    "魔兽世界",
    "World of Warcraft",
    "Wow",
    "WoW",
]


class WoWEnterSpammer:
    """后台向魔兽世界窗口发送随机间隔回车键的工具类。"""

    def __init__(self, min_delay_ms: int = MIN_DELAY_MS, max_delay_ms: int = MAX_DELAY_MS):
        if min_delay_ms > max_delay_ms:
            min_delay_ms, max_delay_ms = max_delay_ms, min_delay_ms
        self.min_delay_ms = max(50, min_delay_ms)
        self.max_delay_ms = max(self.min_delay_ms, max_delay_ms)
        self.running = False
        self.alive = True
        self.wow_hwnd = None
        self.wow_title = ""
        self.spam_thread = None
        self.total_sent = 0
        self.lock = threading.Lock()

    def find_wow_window(self) -> tuple[int | None, str]:
        """遍历所有可见窗口，查找魔兽世界客户端窗口句柄。"""
        found_hwnd = None
        found_title = ""

        def enum_callback(hwnd, _lparam):
            nonlocal found_hwnd, found_title
            if not IsWindowVisible(hwnd):
                return True

            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            for wow_title in WOW_TITLES:
                if wow_title.lower() in title.lower():
                    found_hwnd = hwnd
                    found_title = title
                    return False  # 找到后停止枚举
            return True

        EnumWindows(WNDENUMPROC(enum_callback), 0)
        return found_hwnd, found_title

    def send_enter(self, hwnd: int) -> bool:
        """通过 PostMessageW 向指定窗口发送回车键（支持后台），按下时长随机化。"""
        if not hwnd or not IsWindow(hwnd):
            return False
        try:
            # 回车键 LPARAM：扫描码 0x1C
            lparam_down = 0x001C0001
            lparam_up   = 0xC01C0001

            ok1 = PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, lparam_down)
            hold_sec = random.uniform(MIN_HOLD_MS, MAX_HOLD_MS) / 1000.0
            time.sleep(hold_sec)
            ok2 = PostMessageW(hwnd, WM_KEYUP, VK_RETURN, lparam_up)
            return bool(ok1 and ok2)
        except Exception:
            return False

    def next_delay_sec(self) -> float:
        """生成不规律的随机等待时间（三角分布 + 偶尔人工停顿）。"""
        # 使用三角分布让大部分间隔落在偏中间区域，偶尔偏快或偏慢，更接近真人节奏
        delay_ms = random.triangular(self.min_delay_ms, self.max_delay_ms)
        if random.random() < PAUSE_CHANCE:
            delay_ms += random.uniform(1500, 3500)
        return delay_ms / 1000.0

    def spam_loop(self):
        """后台发送循环。"""
        while self.alive:
            if not self.running:
                time.sleep(0.05)
                continue

            if self.wow_hwnd is None or not IsWindow(self.wow_hwnd):
                self.wow_hwnd, self.wow_title = self.find_wow_window()
                if self.wow_hwnd is None:
                    self.print_status("⚠ 未找到魔兽世界窗口，1秒后重试...")
                    time.sleep(1.0)
                    continue
                else:
                    self.print_status(f"✅ 已绑定窗口: [{self.wow_title}] (HWND: {self.wow_hwnd})")

            if self.send_enter(self.wow_hwnd):
                with self.lock:
                    self.total_sent += 1
                    count = self.total_sent
                wait_sec = self.next_delay_sec()
                if count % 10 == 0:
                    self.print_status(f"🔨 已发送 {count} 次回车 | 下次间隔: {int(wait_sec * 1000)}ms")
                time.sleep(wait_sec)
            else:
                self.wow_hwnd = None
                self.wow_title = ""
                self.print_status("⚠ 发送失败（窗口可能已关闭），重新查找窗口...")
                time.sleep(1.0)

    def toggle(self):
        """切换开始/暂停状态。"""
        self.running = not self.running
        if self.running:
            self.wow_hwnd, self.wow_title = self.find_wow_window()
            if self.wow_hwnd:
                self.print_status(
                    f"▶ 已启动 | 窗口: [{self.wow_title}] (HWND: {self.wow_hwnd}) | "
                    f"随机间隔: {self.min_delay_ms}~{self.max_delay_ms}ms"
                )
            else:
                self.print_status("▶ 已启动 | ⚠ 暂未找到魔兽世界窗口，正在持续查找...")
        else:
            with self.lock:
                count = self.total_sent
            self.print_status(f"⏸ 已暂停 | 累计发送: {count} 次")

    def stop(self):
        """停止并退出脚本。"""
        self.running = False
        self.alive = False
        with self.lock:
            count = self.total_sent
        self.print_status(f"⏹ 脚本已退出 | 累计发送: {count} 次")

    def print_status(self, msg: str):
        """打印带时间戳的状态日志。"""
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {msg}")

    def start(self):
        """启动后台线程与全局热键监听。"""
        self.print_banner()

        self.spam_thread = threading.Thread(target=self.spam_loop, daemon=True)
        self.spam_thread.start()

        keyboard.on_press_key(HOTKEY_TOGGLE, lambda _: self.toggle(), suppress=False)
        keyboard.on_press_key(HOTKEY_EXIT, lambda _: self.stop(), suppress=False)

        self.print_status("等待指令中... 请按 F6 开始。")

        try:
            while self.alive:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

        print("\n  已退出，祝顺利建号！\n")

    def print_banner(self):
        """打印启动信息面板。"""
        print()
        print("  ╔════════════════════════════════════════════════════════════╗")
        print("  ║   魔兽世界后台抢号回车助手（国服适配 + 随机间隔版）        ║")
        print("  ╠════════════════════════════════════════════════════════════╣")
        print(f"  ║  随机间隔:  {self.min_delay_ms}ms ~ {self.max_delay_ms}ms (含随机按键时长与偶发停顿)  ║")
        print(f"  ║  开始/暂停: {HOTKEY_TOGGLE.upper()}                                             ║")
        print(f"  ║  退出程序:  {HOTKEY_EXIT.upper()}                                             ║")
        print("  ║  工作模式:  PostMessageW 后台投递（不占用键鼠）            ║")
        print("  ╠════════════════════════════════════════════════════════════╣")
        print("  ║  用法: 打开魔兽进入创建角色界面，选好种族/职业并填好名字， ║")
        print("  ║        然后按 F6 开始（需以管理员身份运行本脚本）。        ║")
        print("  ╚════════════════════════════════════════════════════════════╝")
        print()


def main():
    """解析命令行参数并启动。"""
    min_delay = MIN_DELAY_MS
    max_delay = MAX_DELAY_MS

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--min-delay", "--min") and i + 1 < len(args):
            try:
                min_delay = int(args[i + 1])
            except ValueError:
                print(f"  ⚠ 无效的最小间隔: {args[i + 1]}，使用默认值 {MIN_DELAY_MS}ms")
            i += 2
        elif arg in ("--max-delay", "--max") and i + 1 < len(args):
            try:
                max_delay = int(args[i + 1])
            except ValueError:
                print(f"  ⚠ 无效的最大间隔: {args[i + 1]}，使用默认值 {MAX_DELAY_MS}ms")
            i += 2
        elif arg in ("--delay", "-d") and i + 1 < len(args):
            try:
                center = int(args[i + 1])
                min_delay = max(50, int(center * 0.6))
                max_delay = max(min_delay + 100, int(center * 1.6))
            except ValueError:
                print(f"  ⚠ 无效的延迟参数: {args[i + 1]}，使用默认范围")
            i += 2
        elif arg in ("--help", "-h"):
            print("  用法: python wow_enter_spammer.py [--min-delay MS] [--max-delay MS]")
            print("        或: python wow_enter_spammer.py --delay MS (自动围绕该值浮动)")
            print(f"  默认随机范围: {MIN_DELAY_MS}ms ~ {MAX_DELAY_MS}ms")
            print(f"  快捷键: {HOTKEY_TOGGLE.upper()} = 开始/暂停 | {HOTKEY_EXIT.upper()} = 退出")
            sys.exit(0)
        else:
            i += 1

    spammer = WoWEnterSpammer(min_delay_ms=min_delay, max_delay_ms=max_delay)
    spammer.start()


if __name__ == "__main__":
    main()
