#!/usr/bin/env python3
"""
Robot Mission – pure Tkinter
Correct start orientation (East) • Full dZ supports on every visible floor
Slopes belong to both layers + improved triangle sides
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json, math, time, copy
from pathlib import Path
from collections import deque

# ──────────────────────────────────────────────
LEVELS_DIR = Path("levels")
PLAYER_DATA = Path("player_data.json")
TILE = 56
SENSOR_MAX = TILE * 1.15
FPS = 30
DT = 1.0 / FPS
STUCK_TIMEOUT = 5.0
MOVE_DURATION = 1.05
DZ = 12                       # visual vertical offset per layer
SOUTH_WALL_H = 10

EMPTY, START, EXIT, BRIDGE, SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W = range(8)
TILE_NAMES = ["Empty", "Start", "Exit", "Bridge", "Slope N", "Slope S", "Slope E", "Slope W"]

def ensure_dirs():
    LEVELS_DIR.mkdir(exist_ok=True)

def make_level_01():
    w, h = 7, 3
    tiles = [[None] * w for _ in range(h)]
    for x in range(1, 6):
        tiles[1][x] = EMPTY
    tiles[1][1] = START
    tiles[1][5] = EXIT

    vwalls = [[False] * (w + 1) for _ in range(h)]
    vwalls[1][1] = True
    vwalls[1][6] = True

    hwalls = [[False] * w for _ in range(h + 1)]
    for x in range(1, 6):
        hwalls[1][x] = True
        hwalls[2][x] = True

    return {
        "name": "01 – Straight Line",
        "layers": [{"tiles": tiles, "vwalls": vwalls, "hwalls": hwalls}],
        "start": [1.5, 1.5, 0, 0],   # x, y, z, angle_deg (0 = East)
        "exit":  [5.5, 1.5, 0]
    }

def ensure_levels():
    ensure_dirs()
    p = LEVELS_DIR / "level_01.json"
    if not p.exists():
        with open(p, "w", encoding="utf-8") as f:
            json.dump(make_level_01(), f, indent=2)

def load_all_levels():
    ensure_levels()
    levels = []
    for p in sorted(LEVELS_DIR.glob("level_*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        data["_file"] = p.name
        levels.append(data)
    return levels

def load_player():
    if PLAYER_DATA.exists():
        with open(PLAYER_DATA, encoding="utf-8") as f:
            data = json.load(f)
        # migrate old format if needed
        data.setdefault("unlocked", 1)
        data.setdefault("best", {})
        return data
    return {"unlocked": 1, "best": {}}

def save_player(data):
    with open(PLAYER_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ──────────────────────────────────────────────
class World:
    def __init__(self, level_data):
        self.raw = level_data
        self.layers = level_data["layers"]
        self.depth = len(self.layers)
        self.h = len(self.layers[0]["tiles"])
        self.w = len(self.layers[0]["tiles"][0])
        self.start = level_data["start"]
        self.exit  = level_data["exit"]
        self.name  = level_data.get("name", "Unnamed")

    def tile(self, x, y, z):
        ix, iy, iz = int(x), int(y), int(z)
        if not (0 <= iz < self.depth and 0 <= iy < self.h and 0 <= ix < self.w):
            return None
        return self.layers[iz]["tiles"][iy][ix]

    def has_vwall(self, x, y, z):
        ix, iy, iz = int(round(x)), int(y), int(z)
        if not (0 <= iz < self.depth and 0 <= iy < self.h and 0 <= ix <= self.w):
            return True
        return bool(self.layers[iz]["vwalls"][iy][ix])

    def has_hwall(self, x, y, z):
        ix, iy, iz = int(x), int(round(y)), int(z)
        if not (0 <= iz < self.depth and 0 <= iy <= self.h and 0 <= ix < self.w):
            return True
        return bool(self.layers[iz]["hwalls"][iy][ix])

    def is_traversable(self, x, y, z):
        return self.tile(x, y, z) is not None

    def get_slope(self, x, y, z):
        """Return (dx, dy) of the slope or None."""
        t = self.tile(x, y, z)
        return {
            SLOPE_N: (0, -1),
            SLOPE_S: (0,  1),
            SLOPE_E: (1,  0),
            SLOPE_W: (-1, 0)
        }.get(t)

# ──────────────────────────────────────────────
class Robot:
    def __init__(self, world):
        self.world = world
        self.reset()

    def reset(self):
        # Always use the level’s start data; force East (0°) if angle missing
        sx, sy, sz, *rest = self.world.start
        ang_deg = rest[0] if rest else 0
        self.x = float(sx)
        self.y = float(sy)
        self.z = float(sz)
        self.angle = math.radians(ang_deg)          # 0 = East
        self.alive = True
        self.finished = False
        self.stuck_timer = 0.0
        self.last_pos = (self.x, self.y, self.z)
        self.visited = set()
        self.distance = 0.0
        self.start_time = None

        self.moving = False
        self.move_t = 0.0
        self.from_x = self.x
        self.from_y = self.y
        self.to_x = self.x
        self.to_y = self.y

        # 6 sensors:
        #   F, L, R, FL, FR  → horizontal rays
        #   FB               → vertical (floor) ray
        self.sensors = {
            "F":  {"off": 0.0,                 "vert": False, "hit": False, "len": SENSOR_MAX},
            "L":  {"off": math.radians(-90),   "vert": False, "hit": False, "len": SENSOR_MAX},
            "R":  {"off": math.radians( 90),   "vert": False, "hit": False, "len": SENSOR_MAX},
            "FL": {"off": math.radians(-32),   "vert": False, "hit": False, "len": SENSOR_MAX},
            "FR": {"off": math.radians( 32),   "vert": False, "hit": False, "len": SENSOR_MAX},
            "FB": {"off": 0.0,                 "vert": True,  "hit": False, "len": TILE * 0.65},
        }

    def update_sensors(self):
        for s in self.sensors.values():
            s["hit"] = False
            s["len"] = SENSOR_MAX if not s["vert"] else TILE * 0.65
            ang = self.angle + s["off"]
            dx, dy = math.cos(ang), math.sin(ang)
            steps = 16
            for i in range(1, steps + 1):
                t = i / steps
                if s["vert"]:
                    px = self.x + dx * 0.4
                    py = self.y + dy * 0.4
                    pz = self.z - t * 0.85
                    if not self.world.is_traversable(px, py, pz):
                        s["hit"] = True
                        s["len"] = t * TILE * 0.65
                        break
                else:
                    px = self.x + dx * t * 1.25
                    py = self.y + dy * t * 1.25
                    if self._ray_hits_wall(self.x, self.y, px, py, self.z):
                        s["hit"] = True
                        s["len"] = t * SENSOR_MAX
                        break

    def _ray_hits_wall(self, x0, y0, x1, y1, z):
        dx, dy = x1 - x0, y1 - y0
        steps = max(8, int(math.hypot(dx, dy) * 10))
        for i in range(1, steps + 1):
            t = i / steps
            cx = x0 + dx * t
            cy = y0 + dy * t
            prev_t = (i - 1) / steps
            if int(cx) != int(x0 + dx * prev_t) or abs(cx - round(cx)) < 0.05:
                if self.world.has_vwall(round(cx), cy, z):
                    return True
            if int(cy) != int(y0 + dy * prev_t) or abs(cy - round(cy)) < 0.05:
                if self.world.has_hwall(cx, round(cy), z):
                    return True
        return False

    def apply_command(self, cmd, dt):
        if not self.alive or self.finished or self.moving:
            return
        if cmd == "forward":
            tx = self.x + math.cos(self.angle)
            ty = self.y + math.sin(self.angle)
            if self._ray_hits_wall(self.x, self.y, tx, ty, self.z):
                self.alive = False
                return
            self._start_move(tx, ty)
        elif cmd == "reverse":
            tx = self.x - math.cos(self.angle)
            ty = self.y - math.sin(self.angle)
            if self._ray_hits_wall(self.x, self.y, tx, ty, self.z):
                self.alive = False
                return
            self._start_move(tx, ty)
        elif cmd == "turn_left":
            self.angle -= math.pi / 2
        elif cmd == "turn_right":
            self.angle += math.pi / 2

    def _start_move(self, tx, ty):
        self.moving = True
        self.move_t = 0.0
        self.from_x, self.from_y = self.x, self.y
        self.to_x, self.to_y = tx, ty

    def _resolve_height(self):
        """
        Called after every completed one-tile move.
        Handles proper adjacent slope pairs and falling.
        """
        slope = self.world.get_slope(self.x, self.y, self.z)

        if slope is not None:
            # slope = descent direction (points toward the lower end)
            facing_x = math.cos(self.angle)
            facing_y = math.sin(self.angle)
            alignment = facing_x * slope[0] + facing_y * slope[1]

            def has_adjacent_slope(target_z):
                """True only when the immediate neighbour layer has the same slope type."""
                if not (0 <= target_z < self.world.depth):
                    return False
                return self.world.get_slope(self.x, self.y, target_z) == slope

            # ── going DOWN the slope (toward the low end) ──────────
            if alignment > 0.4:
                target_z = self.z - 1
                if has_adjacent_slope(target_z) and self.world.is_traversable(
                        self.x, self.y, target_z):
                    self.z = target_z
                else:
                    # no valid lower pair → fall
                    if (self.z > 0 and
                            self.world.is_traversable(self.x, self.y, self.z - 1)):
                        self.z -= 1
                    else:
                        self.alive = False
                return

            # ── going UP the slope (from the low end toward the high end) ──
            elif alignment < -0.4:
                target_z = self.z + 1
                if has_adjacent_slope(target_z) and self.world.is_traversable(
                        self.x, self.y, target_z):
                    self.z = target_z          # climb one layer
                # else: stay on current layer (blocked or no pair)
                return

            # ── moving roughly perpendicular to the slope ──────────
            else:
                if (self.z > 0 and
                        self.world.is_traversable(self.x, self.y, self.z - 1)):
                    self.z -= 1
                else:
                    self.alive = False
                return

        # ── ordinary floor tile ────────────────────────────────────
        if not self.world.is_traversable(self.x, self.y, self.z):
            if (self.z > 0 and
                    self.world.is_traversable(self.x, self.y, self.z - 1)):
                self.z -= 1
            else:
                self.alive = False

    def physics_step(self, dt):
        if not self.alive or self.finished:
            return
        if self.start_time is None:
            self.start_time = time.time()

        if self.moving:
            self.move_t += dt
            t = min(1.0, self.move_t / MOVE_DURATION)
            t = t * t * (3 - 2 * t)          # smoothstep
            self.x = self.from_x + (self.to_x - self.from_x) * t
            self.y = self.from_y + (self.to_y - self.from_y) * t
            if self.move_t >= MOVE_DURATION:
                self.x, self.y = self.to_x, self.to_y
                self.moving = False
                self.distance += 1.0
                self.visited.add((int(self.x), int(self.y), int(self.z)))
                self._resolve_height()

        ex, ey, ez = self.world.exit
        if abs(self.x - ex) < 0.4 and abs(self.y - ey) < 0.4 and abs(self.z - ez) < 0.5:
            self.finished = True
            return
        if math.hypot(self.x - self.last_pos[0], self.y - self.last_pos[1]) < 0.01 and not self.moving:
            self.stuck_timer += dt
        else:
            self.stuck_timer = 0
            self.last_pos = (self.x, self.y, self.z)
        if self.stuck_timer > STUCK_TIMEOUT:
            self.alive = False
        self.update_sensors()

# ──────────────────────────────────────────────
class Block:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.sensor = kw.get("sensor", None)          # "F", "L", "R", "FL", …
        self.n = kw.get("n", 1)
        self.body = kw.get("body", [])
        self.true_branch = kw.get("true_branch", [])
        self.false_branch = kw.get("false_branch", [])
        self.condition = kw.get("condition", [])      # list of sensor / logic blocks
        self.id = id(self)

class Interpreter:
    def __init__(self, robot, program):
        self.robot = robot
        self.program = program
        self.stack = []          # list of (blocks_list, index)
        self.running = False

    def start(self):
        self.robot.update_sensors()
        self.stack = [(self.program.blocks, 0)]
        self.running = True

    def stop(self):
        self.running = False
        self.stack.clear()

    # ── condition evaluator (handles sensors + ¬ ∧ ∨) ──────────
    def _eval_condition(self, condition):
        if not condition:
            return False

        result = None
        pending_not = False
        pending_op = None          # "and" | "or"

        for cb in condition:
            if cb.kind.startswith("sensor_"):
                key = getattr(cb, "sensor", None) or cb.kind.split("_", 1)[-1]
                val = bool(self.robot.sensors.get(key, {}).get("hit", False))
                if pending_not:
                    val = not val
                    pending_not = False

                if result is None:
                    result = val
                elif pending_op == "and":
                    result = result and val
                    pending_op = None
                elif pending_op == "or":
                    result = result or val
                    pending_op = None
                else:
                    result = val          # no operator → replace

            elif cb.kind == "not":
                pending_not = True
            elif cb.kind == "and":
                pending_op = "and"
            elif cb.kind == "or":
                pending_op = "or"

        return bool(result) if result is not None else False

    # ── one step of the program ────────────────────────────────
    def tick(self, dt):
        if not self.running or self.robot.moving:
            return

        while self.stack:
            blocks, idx = self.stack[-1]

            if idx >= len(blocks):
                self.stack.pop()
                continue

            b = blocks[idx]

            # ── primitive movement ────────────────────────────
            if b.kind in ("forward", "reverse", "turn_left", "turn_right"):
                self.stack[-1] = (blocks, idx + 1)
                self.robot.apply_command(b.kind, dt)
                return                          # one command per tick

            # ── Repeat N times ────────────────────────────────
            elif b.kind == "repeat_n":
                self.stack[-1] = (blocks, idx + 1)
                n = max(1, int(getattr(b, "n", 1)))
                body = getattr(b, "body", None) or []
                for _ in range(n):
                    self.stack.append((body, 0))
                # continue → start executing the first body copy

            # ── If ────────────────────────────────────────────
            elif b.kind == "if":
                self.stack[-1] = (blocks, idx + 1)
                cond = self._eval_condition(getattr(b, "condition", []))
                branch = (getattr(b, "true_branch", None) or []) if cond \
                         else (getattr(b, "false_branch", None) or [])
                if branch:
                    self.stack.append((branch, 0))

            # ── Repeat until <condition> ──────────────────────
            elif b.kind == "repeat_until":
                cond = self._eval_condition(getattr(b, "condition", []))
                if cond:
                    # condition true → leave the loop
                    self.stack[-1] = (blocks, idx + 1)
                else:
                    body = getattr(b, "body", None) or []
                    if body:
                        # do NOT advance idx; after body finishes
                        # we will re-evaluate the same repeat_until
                        self.stack.append((body, 0))
                    else:
                        # empty body would spin forever
                        self.stack[-1] = (blocks, idx + 1)

            # ── unknown / sensor-or-logic that leaked out ─────
            else:
                self.stack[-1] = (blocks, idx + 1)

        # stack empty → program finished
        self.running = False

class Program:
    def __init__(self):
        self.blocks = []
        self.history = []
        self.future = []
    def push(self):
        self.history.append(copy.deepcopy(self.blocks))
        self.future.clear()
    def undo(self):
        if self.history:
            self.future.append(self.blocks)
            self.blocks = self.history.pop()
    def redo(self):
        if self.future:
            self.history.append(self.blocks)
            self.blocks = self.future.pop()
    def reset(self):
        self.push()
        self.blocks = []

def block_to_dict(b):
    d = {"kind": b.kind}
    if b.kind == "repeat_n":
        d["n"] = getattr(b, "n", 1)
        d["body"] = [block_to_dict(x) for x in getattr(b, "body", [])]
    elif b.kind == "if":
        d["condition"] = [block_to_dict(x) for x in getattr(b, "condition", [])]
        d["true_branch"] = [block_to_dict(x) for x in getattr(b, "true_branch", [])]
        d["false_branch"] = [block_to_dict(x) for x in getattr(b, "false_branch", [])]
    elif b.kind == "repeat_until":
        d["condition"] = [block_to_dict(x) for x in getattr(b, "condition", [])]
        d["body"] = [block_to_dict(x) for x in getattr(b, "body", [])]
    elif b.kind.startswith("sensor_"):
        d["sensor"] = getattr(b, "sensor", b.kind.split("_", 1)[-1])
    return d


def dict_to_block(d):
    b = Block(d["kind"])
    if d["kind"] == "repeat_n":
        b.n = d.get("n", 1)
        b.body = [dict_to_block(x) for x in d.get("body", [])]
    elif d["kind"] == "if":
        b.condition = [dict_to_block(x) for x in d.get("condition", [])]
        b.true_branch = [dict_to_block(x) for x in d.get("true_branch", [])]
        b.false_branch = [dict_to_block(x) for x in d.get("false_branch", [])]
    elif d["kind"] == "repeat_until":
        b.condition = [dict_to_block(x) for x in d.get("condition", [])]
        b.body = [dict_to_block(x) for x in d.get("body", [])]
    elif d["kind"].startswith("sensor_"):
        b.sensor = d.get("sensor", d["kind"].split("_", 1)[-1])
    return b

# ──────────────────────────────────────────────
class AlgorithmEditor(tk.Toplevel):
    def __init__(self, master, program, on_close=None, readonly=False):
        super().__init__(master)
        self.title("Algorithm Viewer" if readonly else "Algorithm Editor")
        self.geometry("1100x700")
        self.program = program
        self.on_close = on_close
        self.readonly = readonly
        self.protocol("WM_DELETE_WINDOW", self._close)

        # ── Toolbar ──
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=4, pady=4)

        if not readonly:
            ttk.Button(toolbar, text="↶ Undo", width=8, command=self._undo).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="↷ Redo", width=8, command=self._redo).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="⟲ Reset", width=8, command=self._reset).pack(side=tk.LEFT, padx=2)
            ttk.Label(toolbar, text="  Drag from palette.  Right-click deletes.  "
                                    "Conditions go to the right of If / Repeat-until.").pack(side=tk.LEFT, padx=12)
        else:
            ttk.Label(toolbar, text="  Read-only view of the saved solution algorithm.").pack(side=tk.LEFT, padx=12)
        # ── Main area ──
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)
        
        if not readonly:
            # ── Scrollable Palette ──
            pal_outer = ttk.LabelFrame(main, text="Blocks", padding=2)
            pal_outer.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)

            self.pal_canvas = tk.Canvas(pal_outer, width=148, highlightthickness=0,
                                        bg=self.cget("bg"))
            pal_vsb = ttk.Scrollbar(pal_outer, orient="vertical",
                                    command=self.pal_canvas.yview)
            self.pal_canvas.configure(yscrollcommand=pal_vsb.set)

            pal_vsb.pack(side=tk.RIGHT, fill=tk.Y)
            self.pal_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            self.pal_frame = ttk.Frame(self.pal_canvas)
            self.pal_window = self.pal_canvas.create_window((0, 0), window=self.pal_frame,
                                                            anchor="nw")

            def _on_pal_configure(event):
                # Update scrollregion when the inner frame changes size
                self.pal_canvas.configure(scrollregion=self.pal_canvas.bbox("all"))
                # Keep the window width matched to the canvas
                self.pal_canvas.itemconfigure(self.pal_window, width=event.width)

            self.pal_frame.bind("<Configure>", _on_pal_configure)

            def _on_pal_canvas_configure(event):
                self.pal_canvas.itemconfigure(self.pal_window, width=event.width)

            self.pal_canvas.bind("<Configure>", _on_pal_canvas_configure)

            # Mouse-wheel scrolling for the palette (Windows / macOS)
            def _on_pal_mousewheel(event):
                self.pal_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

            self.pal_canvas.bind("<MouseWheel>", _on_pal_mousewheel)
            self.pal_frame.bind("<MouseWheel>", _on_pal_mousewheel)

            # Also support Linux-style buttons
            self.pal_canvas.bind("<Button-4>", lambda e: self.pal_canvas.yview_scroll(-1, "units"))
            self.pal_canvas.bind("<Button-5>", lambda e: self.pal_canvas.yview_scroll(1, "units"))
            self.pal_frame.bind("<Button-4>", lambda e: self.pal_canvas.yview_scroll(-1, "units"))
            self.pal_frame.bind("<Button-5>", lambda e: self.pal_canvas.yview_scroll(1, "units"))

            self.palette_items = [
                ("Forward",      "forward"),
                ("Reverse",      "reverse"),
                ("Turn Left",    "turn_left"),
                ("Turn Right",   "turn_right"),
                ("Repeat N×",    "repeat_n"),
                ("If …",         "if"),
                ("Repeat until", "repeat_until"),
                ("─ sensors ─",  None),
                ("↑  Forward",   "sensor_F"),
                ("←  Left",      "sensor_L"),
                ("→  Right",     "sensor_R"),
                ("↖  FL",        "sensor_FL"),
                ("↗  FR",        "sensor_FR"),
                ("↓  Floor",     "sensor_FB"),
                ("─ logic ─",    None),
                ("¬  NOT",       "not"),
                ("∧  AND",       "and"),
                ("∨  OR",        "or"),
            ]

            for label, kind in self.palette_items:
                if kind is None:
                    ttk.Label(self.pal_frame, text=label, foreground="#888").pack(pady=4, padx=4)
                    continue
                btn = ttk.Button(self.pal_frame, text=label, width=14)
                btn.kind = kind
                btn.pack(pady=2, padx=4)
                btn.bind("<ButtonPress-1>", self._on_palette_press)
                btn.bind("<B1-Motion>", self._on_palette_motion)
                btn.bind("<ButtonRelease-1>", self._on_palette_release)
                # Let the wheel work while hovering a button too
                btn.bind("<MouseWheel>", _on_pal_mousewheel)
                btn.bind("<Button-4>", lambda e: self.pal_canvas.yview_scroll(-1, "units"))
                btn.bind("<Button-5>", lambda e: self.pal_canvas.yview_scroll(1, "units"))

        # ── Sequence canvas + scrollbars ──
        seq_frame = ttk.Frame(main)
        seq_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.canvas = tk.Canvas(seq_frame, bg="#1e1e2e", highlightthickness=0)
        vsb = ttk.Scrollbar(seq_frame, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(seq_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if not readonly:
            self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # ── Drag state ──
        self.drag = {
            "active": False,
            "kind": None,
        }

        self.layout = []
        self.redraw()

    # ──────────────────────────────────────────────
    def _close(self):
        if self.on_close:
            self.on_close()
        self.destroy()

    def _undo(self):
        self.program.undo()
        self.redraw()

    def _redo(self):
        self.program.redo()
        self.redraw()

    def _reset(self):
        self.program.reset()
        self.redraw()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ──────────────────────────────────────────────
    # Drag state machine
    # ──────────────────────────────────────────────
    def _on_palette_press(self, event):
        self.drag["active"] = True
        self.drag["kind"] = event.widget.kind

    def _on_palette_motion(self, event):
        pass

    def _on_palette_release(self, event):
        if not self.drag["active"]:
            return

        kind = self.drag["kind"]
        self.drag["active"] = False
        self.drag["kind"] = None

        # IMPORTANT: use global pointer position → sequence-canvas coordinates.
        # This is independent of palette scrolling.
        try:
            cx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            cy = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            canvas_x = self.canvas.canvasx(cx)
            canvas_y = self.canvas.canvasy(cy)
        except tk.TclError:
            return

        target_list = self.program.blocks
        insert_idx = len(target_list)
        is_condition = False

        for info in reversed(self.layout):
            if info["type"] != "zone":
                continue
            x0, y0, x1, y1 = info["bbox"]
            if x0 <= canvas_x <= x1 and y0 <= canvas_y <= y1:
                target_list = info["list"]
                insert_idx = info.get("index", len(target_list))
                is_condition = info.get("is_condition", False)
                break

        is_sensor_or_logic = kind.startswith("sensor_") or kind in ("not", "and", "or")

        if is_condition and not is_sensor_or_logic:
            return
        if not is_condition and is_sensor_or_logic:
            return

        self.program.push()
        newb = Block(kind)

        if kind == "repeat_n":
            newb.n = 2
            newb.body = []
        elif kind == "if":
            newb.condition = []
            newb.true_branch = []
            newb.false_branch = []
        elif kind == "repeat_until":
            newb.condition = []
            newb.body = []
        elif kind.startswith("sensor_"):
            newb.sensor = kind.split("_")[1]

        target_list.insert(insert_idx, newb)
        self.redraw()

    # ──────────────────────────────────────────────
    def _on_right_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        for info in reversed(self.layout):
            if info["type"] != "block":
                continue
            x0, y0, x1, y1 = info["bbox"]
            if x0 <= canvas_x <= x1 and y0 <= canvas_y <= y1:
                self.program.push()
                try:
                    info["list"].remove(info["block"])
                except ValueError:
                    pass
                self.redraw()
                return

    # ──────────────────────────────────────────────
    # Drawing helpers
    # ──────────────────────────────────────────────
    def redraw(self):
        self.canvas.delete("all")
        self.layout = []
        self._y = 20
        self._number = [1]

        self._draw_sequence(self.program.blocks, x=30, numbered=True)

        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(0, 0, bbox[2] + 40, bbox[3] + 40))

    def _draw_drop_zone(self, x, blocks, index, is_condition=False, width=160, height=14):
        y = self._y
        self.canvas.create_rectangle(
            x, y, x + width, y + height,
            outline="#45475a", dash=(3, 3), fill="#313244"
        )
        self.layout.append({
            "type": "zone",
            "bbox": (x, y, x + width, y + height),
            "list": blocks,
            "index": index,
            "is_condition": is_condition
        })
        self._y += height + 2

    def _draw_sequence(self, blocks, x, numbered=True):
        zone_w = 160

        if not blocks:
            h = 36
            self.canvas.create_rectangle(
                x, self._y, x + zone_w, self._y + h,
                outline="#585b70", dash=(4, 4)
            )
            self.layout.append({
                "type": "zone",
                "bbox": (x, self._y, x + zone_w, self._y + h),
                "list": blocks,
                "index": 0,
                "is_condition": False
            })
            self._y += h + 10
            return

        self._draw_drop_zone(x, blocks, 0, width=zone_w)

        for i, block in enumerate(blocks):
            self._draw_block(block, x, numbered, blocks, i)
            self._draw_drop_zone(x, blocks, i + 1, width=zone_w)

    def _block_label(self, kind):
        labels = {
            "forward": "Forward",
            "reverse": "Reverse",
            "turn_left": "Turn Left",
            "turn_right": "Turn Right",
            "repeat_n": "Repeat",
            "if": "If",
            "repeat_until": "Repeat until",
            "sensor_F":  "↑",
            "sensor_L":  "←",
            "sensor_R":  "→",
            "sensor_FL": "↖",
            "sensor_FR": "↗",
            "sensor_FB": "↓",
            "not": "¬",
            "and": "∧",
            "or":  "∨",
        }
        return labels.get(kind, kind)

    def _color(self, kind):
        colors = {
            "forward": "#89b4fa", "reverse": "#f38ba8",
            "turn_left": "#a6e3a1", "turn_right": "#f9e2af",
            "repeat_n": "#fab387", "if": "#cba6f7", "repeat_until": "#f5c2e7",
            "sensor_F":  "#94e2d5", "sensor_L":  "#94e2d5", "sensor_R":  "#94e2d5",
            "sensor_FL": "#94e2d5", "sensor_FR": "#94e2d5", "sensor_FB": "#94e2d5",
            "not": "#f5c2e7", "and": "#f5c2e7", "or": "#f5c2e7"
        }
        return colors.get(kind, "#6c7086")

    def _draw_block(self, block, x, numbered, parent_list, index):
        y = self._y
        w = 150
        h = 34

        if numbered and not (block.kind.startswith("sensor_") or block.kind in ("not", "and", "or")):
            cx = x - 20
            self.canvas.create_oval(cx - 11, y + 6, cx + 11, y + 28,
                                    fill="#cba6f7", outline="#cdd6f4")
            self.canvas.create_text(cx, y + 17, text=str(self._number[0]),
                                    fill="#1e1e2e", font=("Segoe UI", 9, "bold"))
            self._number[0] += 1

        col = self._color(block.kind)

        self.canvas.create_rectangle(x, y, x + w, y + h,
                                     fill=col, outline="#cdd6f4", width=2)

        if block.kind == "repeat_n":
            label = f"Repeat {getattr(block, 'n', 2)}×"
        else:
            label = self._block_label(block.kind)

        self.canvas.create_text(x + w / 2, y + h / 2, text=label,
                                fill="#1e1e2e", font=("Segoe UI", 10, "bold"))

        self.layout.append({
            "type": "block",
            "bbox": (x, y, x + w, y + h),
            "block": block,
            "list": parent_list
        })

        if block.kind == "repeat_n":
            entry = ttk.Entry(self.canvas, width=3)
            entry.insert(0, str(getattr(block, "n", 2)))
            if self.readonly:
                entry.configure(state="readonly")
            else:
                entry.bind("<KeyRelease>", lambda e, b=block, ent=entry: self._set_n(b, ent))
                entry.bind("<FocusOut>",   lambda e, b=block, ent=entry: self._set_n(b, ent))
                entry.bind("<Return>",     lambda e, b=block, ent=entry: self._set_n(b, ent))
            self.canvas.create_window(x + w + 28, y + h / 2, window=entry)

        self._y += h + 4

        if block.kind in ("if", "repeat_until"):
            if not hasattr(block, "condition"):
                block.condition = []
            self._draw_condition_row(block.condition, x + w + 16, y)

        if block.kind in ("repeat_n", "repeat_until"):
            body = getattr(block, "body", [])
            self.canvas.create_line(x + 12, y + h, x + 12, self._y + 4, fill="#585b70", width=2)
            self._draw_sequence(body, x + 28, numbered=True)

        if block.kind == "if":
            true_branch = getattr(block, "true_branch", [])
            self.canvas.create_line(x + 12, y + h, x + 12, self._y + 4, fill="#585b70", width=2)
            self.canvas.create_text(x + 40, self._y - 2, text="then", fill="#a6e3a1",
                                    font=("Segoe UI", 8), anchor="w")
            self._draw_sequence(true_branch, x + 28, numbered=True)

            false_branch = getattr(block, "false_branch", [])
            self.canvas.create_text(x + 40, self._y - 2, text="else", fill="#f38ba8",
                                    font=("Segoe UI", 8), anchor="w")
            self._draw_sequence(false_branch, x + 28, numbered=True)

    def _draw_condition_row(self, condition, x, y):
        ch = 32
        bw = 42
        zone_w = 16

        self.canvas.create_rectangle(x, y, x + zone_w, y + ch,
                                     outline="#45475a", dash=(2, 2), fill="#313244")
        self.layout.append({
            "type": "zone",
            "bbox": (x, y, x + zone_w, y + ch),
            "list": condition,
            "index": 0,
            "is_condition": True
        })
        cx = x + zone_w + 2

        for i, cb in enumerate(condition):
            self.canvas.create_rectangle(cx, y + 3, cx + bw, y + ch - 3,
                                         fill=self._color(cb.kind), outline="#cdd6f4")
            lbl = self._block_label(cb.kind)
            self.canvas.create_text(cx + bw / 2, y + ch / 2, text=lbl,
                                    fill="#1e1e2e", font=("Segoe UI", 12, "bold"))
            self.layout.append({
                "type": "block",
                "bbox": (cx, y + 3, cx + bw, y + ch - 3),
                "block": cb,
                "list": condition
            })
            cx += bw + 2

            self.canvas.create_rectangle(cx, y, cx + zone_w, y + ch,
                                         outline="#45475a", dash=(2, 2), fill="#313244")
            self.layout.append({
                "type": "zone",
                "bbox": (cx, y, cx + zone_w, y + ch),
                "list": condition,
                "index": i + 1,
                "is_condition": True
            })
            cx += zone_w + 2

        if not condition:
            self.canvas.create_rectangle(cx, y, cx + 110, y + ch,
                                         outline="#585b70", dash=(3, 3))
            self.layout.append({
                "type": "zone",
                "bbox": (cx, y, cx + 110, y + ch),
                "list": condition,
                "index": 0,
                "is_condition": True
            })

    def _set_n(self, block, entry):
        try:
            val = int(entry.get())
            if val < 1:
                val = 1
            if getattr(block, "n", None) != val:
                block.n = val
                self.after_idle(self.redraw)
        except ValueError:
            pass
# ──────────────────────────────────────────────
class LevelEditor(tk.Toplevel):
    def __init__(self, master, level_data=None, level_path=None):
        super().__init__(master)
        self.title("Level Editor")
        self.geometry("1150x750")

        self.level_path = level_path
        self.original_name = None

        if level_data is not None:
            # deep-copy so edits don't mutate the cached level list
            self.layers = copy.deepcopy(level_data["layers"])
            self.depth = len(self.layers)
            self.h = len(self.layers[0]["tiles"])
            self.w = len(self.layers[0]["tiles"][0])
            self.original_name = level_data.get("name", "")
        else:
            self.w = 12
            self.h = 8
            self.depth = 1
            self.layers = [self._new_layer()]

        self.cur_layer = 0
        self.view_mode = "stack"

        self.tool = "empty"
        self.empty_subtype = EMPTY
        self.slope_dir = "S"
        self.slope_link = "bottom"

        # ── Toolbar ──
        tb = ttk.Frame(self)
        tb.pack(fill=tk.X, padx=4, pady=4)

        ttk.Label(tb, text="Tool:").pack(side=tk.LEFT)
        self.tool_var = tk.StringVar(value="Empty / Floor")
        tool_cb = ttk.Combobox(tb, textvariable=self.tool_var,
                               values=["Empty / Floor", "Slope", "Wall"],
                               width=14, state="readonly")
        tool_cb.pack(side=tk.LEFT, padx=4)
        tool_cb.bind("<<ComboboxSelected>>", self._on_tool_change)

        self.sec_frame = ttk.Frame(tb)
        self.sec_frame.pack(side=tk.LEFT, padx=12)

        self.empty_var = tk.StringVar(value="Empty")
        self.empty_cb = ttk.Combobox(self.sec_frame, textvariable=self.empty_var,
                                     values=["Empty", "Bridge", "Start", "Exit"],
                                     width=8, state="readonly")
        self.empty_cb.bind("<<ComboboxSelected>>", self._on_empty_change)

        self.dir_var = tk.StringVar(value="South ▼")
        self.dir_cb = ttk.Combobox(self.sec_frame, textvariable=self.dir_var,
                                   values=["North ▲", "South ▼", "East ▶", "West ◀"],
                                   width=10, state="readonly")
        self.dir_cb.bind("<<ComboboxSelected>>", self._on_dir_change)

        self.link_var = tk.StringVar(value="Bottom")
        self.link_cb = ttk.Combobox(self.sec_frame, textvariable=self.link_var,
                                    values=["Bottom", "Top"],
                                    width=8, state="readonly")
        self.link_cb.bind("<<ComboboxSelected>>", self._on_link_change)

        # View-mode selector
        ttk.Label(tb, text="  View:").pack(side=tk.LEFT, padx=(12, 0))
        self.view_var = tk.StringVar(value="Stack (↓)")
        view_cb = ttk.Combobox(tb, textvariable=self.view_var,
                               values=["Stack (↓)", "Single"],
                               width=12, state="readonly")
        view_cb.pack(side=tk.LEFT, padx=4)
        view_cb.bind("<<ComboboxSelected>>", self._on_view_change)

        save_label = "Save (Override)" if level_path else "Save Level"
        ttk.Button(tb, text=save_label, command=self._save).pack(side=tk.RIGHT, padx=8)

        self._update_secondary()

        # ── Body ──
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        canvas_h = self.h * TILE + 40 + 8 * DZ + SOUTH_WALL_H
        self.cv = tk.Canvas(body, bg="#11111b",
                            width=self.w * TILE + 40,
                            height=canvas_h,
                            highlightthickness=0)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cv.bind("<Button-1>", self._on_left_click)
        self.cv.bind("<Button-3>", self._on_right_click)

        # Right panel
        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        ttk.Label(right, text="Layers", font=("Segoe UI", 11, "bold")).pack(pady=(0, 6))

        self.layer_btn_frame = ttk.Frame(right)
        self.layer_btn_frame.pack(fill=tk.Y, expand=True)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="－ Remove Top Layer",
                   command=self._remove_layer).pack(fill=tk.X, pady=2)

        self._rebuild_layer_buttons()
        self.redraw()

    # ──────────────────────────────────────────
    def _new_layer(self):
        tiles = [[None for _ in range(self.w)] for _ in range(self.h)]
        vwalls = [[False for _ in range(self.w + 1)] for _ in range(self.h)]
        hwalls = [[False for _ in range(self.w)] for _ in range(self.h + 1)]
        return {"tiles": tiles, "vwalls": vwalls, "hwalls": hwalls}

    def _rebuild_layer_buttons(self):
        for w in self.layer_btn_frame.winfo_children():
            w.destroy()

        for z in range(self.depth):
            btn = ttk.Button(
                self.layer_btn_frame,
                text=f"Layer {z}",
                width=10,
                command=lambda zz=z: self._select_layer(zz)
            )
            btn.pack(pady=2, fill=tk.X)
            if z == self.cur_layer:
                btn.state(["pressed"])

        # “+” button always at the bottom of the panel
        ttk.Button(
            self.layer_btn_frame,
            text="＋  Add Layer",
            width=10,
            command=self._add_layer
        ).pack(pady=(8, 2), fill=tk.X)

    def _select_layer(self, z):
        self.cur_layer = max(0, min(z, self.depth - 1))
        self._rebuild_layer_buttons()
        self.redraw()

    def _on_tool_change(self, event=None):
        t = self.tool_var.get()
        if t == "Empty / Floor":
            self.tool = "empty"
        elif t == "Slope":
            self.tool = "slope"
        else:
            self.tool = "wall"
        self._update_secondary()

    def _on_empty_change(self, event=None):
        mapping = {"Empty": EMPTY, "Bridge": BRIDGE, "Start": START, "Exit": EXIT}
        self.empty_subtype = mapping.get(self.empty_var.get(), EMPTY)

    def _on_dir_change(self, event=None):
        mapping = {
            "North ▲": "N", "South ▼": "S",
            "East ▶": "E", "West ◀": "W"
        }
        self.slope_dir = mapping.get(self.dir_var.get(), "S")

    def _on_link_change(self, event=None):
        self.slope_link = "bottom" if self.link_var.get() == "Bottom" else "top"

    def _on_view_change(self, event=None):
        self.view_mode = "stack" if "Stack" in self.view_var.get() else "single"
        self.redraw()

    def _update_secondary(self):
        for child in self.sec_frame.winfo_children():
            child.pack_forget()
        if self.tool == "empty":
            ttk.Label(self.sec_frame, text="Type:").pack(side=tk.LEFT)
            self.empty_cb.pack(side=tk.LEFT, padx=4)
        elif self.tool == "slope":
            ttk.Label(self.sec_frame, text="Dir:").pack(side=tk.LEFT)
            self.dir_cb.pack(side=tk.LEFT, padx=2)
            ttk.Label(self.sec_frame, text="Link:").pack(side=tk.LEFT, padx=(8, 0))
            self.link_cb.pack(side=tk.LEFT, padx=2)

    def _add_layer(self):
        """Add a new top layer and continue any slopes that were on the old top."""
        old_top = self.depth - 1
        new_layer = self._new_layer()

        # Continuity: copy every slope from the previous top layer onto the new layer
        for y in range(self.h):
            for x in range(self.w):
                t = self.layers[old_top]["tiles"][y][x]
                if t in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                    new_layer["tiles"][y][x] = t

        self.layers.append(new_layer)
        self.depth = len(self.layers)
        self.cur_layer = self.depth - 1
        self._rebuild_layer_buttons()
        self.redraw()

    def _remove_layer(self):
        if self.depth <= 1:
            return
        del self.layers[-1]
        self.depth = len(self.layers)
        self.cur_layer = min(self.cur_layer, self.depth - 1)
        self._rebuild_layer_buttons()
        self.redraw()

    def _slope_type(self, direction):
        return {"N": SLOPE_N, "S": SLOPE_S, "E": SLOPE_E, "W": SLOPE_W}[direction]

    def _clear_special(self, special):
        for layer in self.layers:
            for y in range(self.h):
                for x in range(self.w):
                    if layer["tiles"][y][x] == special:
                        layer["tiles"][y][x] = EMPTY

    def _is_restricted(self, x, y, z):
        for zz in range(z + 1, self.depth):
            t = self.layers[zz]["tiles"][y][x]
            if t is None or t == BRIDGE:
                continue
            if t in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                continue
            return True
        return False

    def _remove_slope_pair(self, x, y, z):
        t = self.layers[z]["tiles"][y][x]
        if t not in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
            return
        self.layers[z]["tiles"][y][x] = None
        for dz in (-1, 1):
            nz = z + dz
            if 0 <= nz < self.depth:
                if self.layers[nz]["tiles"][y][x] in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                    self.layers[nz]["tiles"][y][x] = None

    def _place_slope(self, x, y, z, direction, link):
        """Place slope on current layer; link to neighbour only if it already exists.
        Never auto-creates a new layer."""
        st = self._slope_type(direction)
        self.layers[z]["tiles"][y][x] = st
        nz = z - 1 if link == "bottom" else z + 1
        if 0 <= nz < self.depth:
            self.layers[nz]["tiles"][y][x] = st
        # if nz is out of range we simply leave the pair incomplete;
        # user can press “+” later and continuity will be restored

    # ──────────────────────────────────────────
    def _screen_to_tile(self, event_x, event_y):
        lift = self.cur_layer * DZ
        col = (event_x - 20) // TILE
        row = (event_y - 20 + lift) // TILE
        return col, row

    def _on_left_click(self, event):
        col, row = self._screen_to_tile(event.x, event.y)
        if not (0 <= col < self.w and 0 <= row < self.h):
            return

        L = self.layers[self.cur_layer]
        cur = L["tiles"][row][col]

        if self.tool == "wall":
            lift = self.cur_layer * DZ
            lx = (event.x - 20) % TILE
            ly = (event.y - 20 + lift) % TILE
            if lx < 8:
                L["vwalls"][row][col] = not L["vwalls"][row][col]
            elif lx > TILE - 8:
                L["vwalls"][row][col + 1] = not L["vwalls"][row][col + 1]
            elif ly < 8:
                L["hwalls"][row][col] = not L["hwalls"][row][col]
            elif ly > TILE - 8:
                L["hwalls"][row + 1][col] = not L["hwalls"][row + 1][col]
            self.redraw()
            return

        if cur is not None:
            self._configure_tile(col, row, cur)
            return

        if self._is_restricted(col, row, self.cur_layer) and self.tool != "slope":
            return

        if self.tool == "empty":
            if self.empty_subtype == START:
                self._clear_special(START)
            elif self.empty_subtype == EXIT:
                self._clear_special(EXIT)
            L["tiles"][row][col] = self.empty_subtype

        elif self.tool == "slope":
            self._place_slope(col, row, self.cur_layer, self.slope_dir, self.slope_link)

        self.redraw()

    def _configure_tile(self, x, y, current):
        L = self.layers[self.cur_layer]
        if current in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
            self._remove_slope_pair(x, y, self.cur_layer)
            self._place_slope(x, y, self.cur_layer, self.slope_dir, self.slope_link)
        elif current in (EMPTY, BRIDGE, START, EXIT):
            if self.empty_subtype == START:
                self._clear_special(START)
            elif self.empty_subtype == EXIT:
                self._clear_special(EXIT)
            L["tiles"][y][x] = self.empty_subtype
        self.redraw()

    def _on_right_click(self, event):
        col, row = self._screen_to_tile(event.x, event.y)
        if not (0 <= col < self.w and 0 <= row < self.h):
            return

        L = self.layers[self.cur_layer]
        lift = self.cur_layer * DZ
        lx = (event.x - 20) % TILE
        ly = (event.y - 20 + lift) % TILE

        removed_wall = False
        if lx < 10 and L["vwalls"][row][col]:
            L["vwalls"][row][col] = False
            removed_wall = True
        elif lx > TILE - 10 and col + 1 <= self.w and L["vwalls"][row][col + 1]:
            L["vwalls"][row][col + 1] = False
            removed_wall = True
        elif ly < 10 and L["hwalls"][row][col]:
            L["hwalls"][row][col] = False
            removed_wall = True
        elif ly > TILE - 10 and row + 1 <= self.h and L["hwalls"][row + 1][col]:
            L["hwalls"][row + 1][col] = False
            removed_wall = True

        if removed_wall:
            self.redraw()
            return

        cur = L["tiles"][row][col]
        if cur is not None:
            if cur in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                self._remove_slope_pair(col, row, self.cur_layer)
            else:
                L["tiles"][row][col] = None
            self.redraw()

    # ──────────────────────────────────────────
    # Drawing (identical geometry to GameView)
    # ──────────────────────────────────────────
    def _tile_colour(self, t):
        return {
            EMPTY: "#3b3b4f", START: "#a6e3a1", EXIT: "#f38ba8",
            BRIDGE: "#89b4fa",
            SLOPE_N: "#fab387", SLOPE_S: "#fab387",
            SLOPE_E: "#fab387", SLOPE_W: "#fab387"
        }.get(t, "#3b3b4f")

    def _draw_supports(self, px, py, lift):
        if lift <= 0:
            return
        self.cv.create_rectangle(px + 4, py - lift + TILE,
                                 px + 10, py + TILE,
                                 fill="#1a1a24", outline="#11111b")
        self.cv.create_rectangle(px + TILE - 10, py - lift + TILE,
                                 px + TILE - 4, py + TILE,
                                 fill="#1a1a24", outline="#11111b")

    def _draw_bridge(self, px, py, lift):
        self._draw_supports(px, py, lift)
        self.cv.create_rectangle(px + 2, py - lift + 3,
                                 px + TILE - 2, py - lift + TILE - 3,
                                 fill="#6c8cbf", outline="#cdd6f4", width=1)
        for i in range(1, 5):
            yy = py - lift + 3 + i * (TILE - 6) / 5
            self.cv.create_line(px + 4, yy, px + TILE - 4, yy, fill="#45475a", width=1)

    def _draw_slope(self, px, py, t, lift):
        self._draw_supports(px, py, lift)
        s = DZ
        if t == SLOPE_W:
            pts = [px, py - lift, px + TILE, py - lift - s,
                   px + TILE, py + TILE - lift - s, px, py + TILE - lift]
            self.cv.create_polygon([px, py - lift, px, py + TILE - lift, px, py + TILE - lift],
                                   fill="#c07040", outline="#1e1e2e")
            self.cv.create_polygon([px + TILE, py - lift - s, px + TILE, py + TILE - lift - s,
                                    px + TILE, py + TILE - lift],
                                   fill="#c07040", outline="#1e1e2e")
        elif t == SLOPE_E:
            pts = [px, py - lift - s, px + TILE, py - lift,
                   px + TILE, py + TILE - lift, px, py + TILE - lift - s]
            self.cv.create_polygon([px, py - lift - s, px, py + TILE - lift - s, px, py + TILE - lift],
                                   fill="#c07040", outline="#1e1e2e")
            self.cv.create_polygon([px + TILE, py - lift, px + TILE, py + TILE - lift,
                                    px + TILE, py + TILE - lift],
                                   fill="#c07040", outline="#1e1e2e")
        elif t == SLOPE_S:
            pts = [px, py - lift, px + TILE, py - lift,
                   px + TILE, py + TILE - lift - s, px, py + TILE - lift - s]
        elif t == SLOPE_N:
            pts = [px, py - lift - s, px + TILE, py - lift - s,
                   px + TILE, py + TILE - lift, px, py + TILE - lift]
        else:
            return
        self.cv.create_polygon(pts, fill="#e0a070", outline="#1e1e2e", width=1)

    def redraw(self):
        self.cv.delete("all")

        if self.view_mode == "single":
            z_list = [self.cur_layer]
        else:
            z_list = list(range(0, self.cur_layer + 1))

        for z in z_list:
            L = self.layers[z]
            lift = z * DZ

            for y in range(self.h):
                for x in range(self.w):
                    t = L["tiles"][y][x]
                    px = 20 + x * TILE
                    py = 20 + y * TILE

                    if z == self.cur_layer and self._is_restricted(x, y, z) and t is None:
                        self.cv.create_rectangle(
                            px + 4, py - lift + 4,
                            px + TILE - 4, py - lift + TILE - 4,
                            outline="#f38ba8", width=2, dash=(4, 3))
                        self.cv.create_text(px + TILE // 2, py - lift + TILE // 2,
                                            text="✕", fill="#f38ba8",
                                            font=("Segoe UI", 16, "bold"))
                        continue

                    if t is None:
                        continue

                    if t == BRIDGE:
                        self._draw_bridge(px, py, lift)
                    elif t in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                        if z == 0 or self.layers[z - 1]["tiles"][y][x] not in (
                                SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                            self._draw_slope(px, py, t, lift)
                    else:
                        self._draw_supports(px, py, lift)
                        col = self._tile_colour(t)
                        self.cv.create_rectangle(px, py - lift,
                                                 px + TILE, py + TILE - lift,
                                                 fill=col, outline="#45475a")
                        if t == START:
                            self.cv.create_text(px + TILE // 2, py - lift + TILE // 2,
                                                text="S", fill="#1e1e2e",
                                                font=("Segoe UI", 14, "bold"))
                        elif t == EXIT:
                            self.cv.create_text(px + TILE // 2, py - lift + TILE // 2,
                                                text="E", fill="#1e1e2e",
                                                font=("Segoe UI", 14, "bold"))

            for y in range(self.h):
                for x in range(self.w + 1):
                    if L["vwalls"][y][x]:
                        self.cv.create_line(20 + x * TILE, 20 + y * TILE - lift,
                                            20 + x * TILE, 20 + (y + 1) * TILE - lift,
                                            fill="#f38ba8", width=3)
            for y in range(self.h + 1):
                for x in range(self.w):
                    if L["hwalls"][y][x]:
                        yy = 20 + y * TILE - lift
                        self.cv.create_line(20 + x * TILE, yy,
                                            20 + (x + 1) * TILE, yy,
                                            fill="#f38ba8", width=2)
                        self.cv.create_rectangle(20 + x * TILE, yy,
                                                 20 + (x + 1) * TILE, yy + SOUTH_WALL_H,
                                                 fill="#c04060", outline="#f38ba8", width=1)

        # faint grid on the editable layer
        lift = self.cur_layer * DZ
        for y in range(self.h + 1):
            self.cv.create_line(20, 20 + y * TILE - lift,
                                20 + self.w * TILE, 20 + y * TILE - lift,
                                fill="#2a2a3a", width=1)
        for x in range(self.w + 1):
            self.cv.create_line(20 + x * TILE, 20 - lift,
                                20 + x * TILE, 20 + self.h * TILE - lift,
                                fill="#2a2a3a", width=1)

    def _find_special(self, special):
        for z, layer in enumerate(self.layers):
            for y in range(self.h):
                for x in range(self.w):
                    if layer["tiles"][y][x] == special:
                        return (x + 0.5, y + 0.5, z)
        return None

    def _save(self):
        start_pos = self._find_special(START)
        exit_pos  = self._find_special(EXIT)

        if start_pos is None or exit_pos is None:
            messagebox.showerror("Missing tiles",
                                 "A level must contain exactly one Start and one Exit tile.")
            return

        if self.level_path is not None:
            # override existing file
            default_name = self.original_name or self.level_path.stem
            name = simpledialog.askstring("Save", "Level name:",
                                          initialvalue=default_name, parent=self)
            if not name:
                return
            data = {
                "name": name,
                "layers": self.layers,
                "start": [start_pos[0], start_pos[1], start_pos[2], 0],
                "exit":  [exit_pos[0], exit_pos[1], exit_pos[2]]
            }
            with open(self.level_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Updated {self.level_path.name}")
            self.destroy()
            return

        # brand-new level
        name = simpledialog.askstring("Save", "Level name:", parent=self)
        if not name:
            return
        existing = list(LEVELS_DIR.glob("level_*.json"))
        num = len(existing) + 1
        data = {
            "name": f"{num:02d} – {name}",
            "layers": self.layers,
            "start": [start_pos[0], start_pos[1], start_pos[2], 0],
            "exit":  [exit_pos[0], exit_pos[1], exit_pos[2]]
        }
        path = LEVELS_DIR / f"level_{num:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Saved", f"Saved as {path.name}")
        self.destroy()
# ──────────────────────────────────────────────
class GameView(ttk.Frame):
    def __init__(self, master, level_idx, levels, player, on_back,
                 app=None, solution_mode=False, saved_algorithm=None):
        super().__init__(master)
        self.master = master
        self.app = app                    # MainApp reference (for next level)
        self.levels = levels
        self.level_idx = level_idx
        self.player = player
        self.on_back = on_back
        self.solution_mode = solution_mode
        self.world = World(levels[level_idx])
        self.robot = Robot(self.world)
        self.program = Program()
        if saved_algorithm:
            self.program.blocks = [dict_to_block(d) for d in saved_algorithm]
        self.interp = Interpreter(self.robot, self.program)
        self.running = False
        self.view_layer = int(self.robot.z)
        self.follow_robot = True
        self.last_time = time.time()

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=4, pady=4)
        title = self.world.name
        if solution_mode:
            title += "  [Solution Replay]"
        ttk.Label(bar, text=title, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)

        if self.solution_mode:
            ttk.Button(bar, text="View Algorithm", command=self.open_viewer).pack(side=tk.LEFT, padx=6)
        else:
            ttk.Button(bar, text="Edit Algorithm", command=self.open_editor).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="▶ Start / Stop", command=self.toggle_run).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Restart", command=self.restart).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Main Menu", command=self.on_back).pack(side=tk.RIGHT)

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        h = self.world.h * TILE + 40 + self.world.depth * DZ + SOUTH_WALL_H
        self.cv = tk.Canvas(body, bg="#11111b",
                            width=self.world.w * TILE + 40,
                            height=h, highlightthickness=0)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cv.bind("<Button-1>", self._click_robot)

        if self.world.depth > 1:
            right = ttk.Frame(body)
            right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
            ttk.Label(right, text="Top").pack()
            self.layer_var = tk.IntVar(value=self.view_layer)
            self.layer_scale = ttk.Scale(right, from_=self.world.depth - 1, to=0,
                                         orient=tk.VERTICAL, variable=self.layer_var,
                                         command=self._on_slider, length=240)
            self.layer_scale.pack(fill=tk.Y, expand=True, pady=4)
            ttk.Label(right, text="Bottom").pack()
            self.layer_scale.set(self.view_layer)

        self.after(int(1000 / FPS), self.loop)
        self.redraw()

        # auto-start in solution replay mode
        if solution_mode and saved_algorithm:
            self.after(300, self._auto_start)
    def open_viewer(self):
        AlgorithmEditor(self, self.program, readonly=True)
    def _auto_start(self):
        self.robot.reset()
        self.interp = Interpreter(self.robot, self.program)
        self.interp.start()
        self.running = True
        self.follow_robot = True
        self.last_time = time.time()
    def _on_slider(self, v):
        self.view_layer = int(float(v))
        self.follow_robot = False
        self.redraw()

    def open_editor(self):
        if not self.solution_mode:
            AlgorithmEditor(self, self.program)

    def _click_robot(self, e):
        if self.solution_mode:
            return
        lift = int(self.robot.z) * DZ
        rx = 20 + self.robot.x * TILE
        ry = 20 + self.robot.y * TILE - lift
        if abs(e.x - rx) < 22 and abs(e.y - ry) < 22:
            self.open_editor()

    def toggle_run(self):
        if self.running:
            self.running = False
            self.interp.stop()
        else:
            self.robot.reset()
            self.interp = Interpreter(self.robot, self.program)
            self.interp.start()
            self.running = True
            self.follow_robot = True
            self.last_time = time.time()

    def restart(self):
        self.running = False
        self.interp.stop()
        self.robot.reset()
        self.follow_robot = True
        if self.solution_mode:
            self.after(200, self._auto_start)
        self.redraw()

    def loop(self):
        now = time.time()
        dt = min(now - self.last_time, 0.05)
        self.last_time = now

        if self.running:
            self.interp.tick(dt)
            self.robot.physics_step(dt)

            # Always keep the view stacked to the robot’s current layer
            if self.follow_robot:
                new_layer = int(self.robot.z)
                if new_layer != self.view_layer:
                    self.view_layer = new_layer
                    if hasattr(self, "layer_scale"):
                        self.layer_scale.set(self.view_layer)

            if self.robot.finished:
                self.running = False
                self._success()
            elif not self.robot.alive:
                self.running = False
                self._fail("Accident or robot stuck")

        self.redraw()
        self.after(int(1000 / FPS), self.loop)

    def _success(self):
        elapsed = time.time() - (self.robot.start_time or time.time())
        dist = self.robot.distance
        msg = f"Success!\nTime {elapsed:.2f}s | Dist {dist:.1f}"

        if self.solution_mode:
            messagebox.showinfo("Solution finished", msg)
            self.on_back()
            return

        # save algorithm + best stats (never in solution mode)
        lid = str(self.level_idx)
        best = self.player["best"].get(lid, {})
        if "time" not in best or elapsed < best["time"]:
            best["time"] = elapsed
        if "dist" not in best or dist < best["dist"]:
            best["dist"] = dist
        best["algorithm"] = [block_to_dict(b) for b in self.program.blocks]
        self.player["best"][lid] = best

        if self.level_idx + 1 >= self.player["unlocked"]:
            self.player["unlocked"] = self.level_idx + 2
        save_player(self.player)

        if messagebox.askyesno("Level Complete", msg + "\n\nNext level?"):
            if self.app and self.level_idx + 1 < len(self.levels):
                self.app.show_game(self.level_idx + 1)
            else:
                messagebox.showinfo("Congratulations", "All levels finished!")
                self.on_back()
        else:
            self.on_back()

    def _fail(self, reason):
        # custom dialog so the negative button is labelled "Exit"
        dlg = tk.Toplevel(self)
        dlg.title("Failed")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        ttk.Label(dlg, text=f"{reason}\n\nWhat do you want to do?",
                  padding=12).pack()
        bf = ttk.Frame(dlg, padding=8)
        bf.pack()
        result = [None]

        def retry():
            result[0] = True
            dlg.destroy()

        def exit_():
            result[0] = False
            dlg.destroy()

        ttk.Button(bf, text="Retry", command=retry, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Exit", command=exit_, width=10).pack(side=tk.LEFT, padx=6)
        dlg.wait_window()

        if result[0]:
            self.restart()
        else:
            self.on_back()

    # ── drawing ──
    def _tile_colour(self, t):
        return {
            EMPTY: "#3b3b4f", START: "#a6e3a1", EXIT: "#f38ba8",
            BRIDGE: "#89b4fa",
            SLOPE_N: "#fab387", SLOPE_S: "#fab387",
            SLOPE_E: "#fab387", SLOPE_W: "#fab387"
        }.get(t, "#3b3b4f")

    def _draw_supports(self, px, py, lift):
        """Full-height support columns for the tile’s own layer."""
        if lift <= 0:
            return
        # left pillar
        self.cv.create_rectangle(px + 4, py - lift + TILE,
                                 px + 10, py + TILE,
                                 fill="#1a1a24", outline="#11111b")
        # right pillar
        self.cv.create_rectangle(px + TILE - 10, py - lift + TILE,
                                 px + TILE - 4, py + TILE,
                                 fill="#1a1a24", outline="#11111b")

    def _draw_bridge(self, px, py, lift):
        self._draw_supports(px, py, lift)
        self.cv.create_rectangle(px + 2, py - lift + 3,
                                 px + TILE - 2, py - lift + TILE - 3,
                                 fill="#6c8cbf", outline="#cdd6f4", width=1)
        for i in range(1, 5):
            yy = py - lift + 3 + i * (TILE - 6) / 5
            self.cv.create_line(px + 4, yy, px + TILE - 4, yy, fill="#45475a", width=1)

    def _draw_slope(self, px, py, t, lift):
        """
        Draw the slope on the BOTTOM layer of the pair.
        All vertical offsets use subtraction of dZ (s).
        Side triangles only for East / West.
        """
        self._draw_supports(px, py, lift)

        s = DZ          # one layer height

        if t == SLOPE_W:          # West
            # top-left  (px,     py - lift)
            # top-right (px+TILE, py - lift - s)
            # bottom-left  (px,     py + TILE - lift)
            # bottom-right (px+TILE, py + TILE - lift - s)
            pts = [
                px,          py - lift,               # top-left
                px + TILE,   py - lift - s,           # top-right
                px + TILE,   py + TILE - lift - s,    # bottom-right
                px,          py + TILE - lift         # bottom-left
            ]
            # side triangles
            self.cv.create_polygon(
                [px, py - lift, px, py + TILE - lift, px, py + TILE - lift],
                fill="#c07040", outline="#1e1e2e")
            self.cv.create_polygon(
                [px + TILE, py - lift - s, px + TILE, py + TILE - lift - s, px + TILE, py + TILE - lift],
                fill="#c07040", outline="#1e1e2e")

        elif t == SLOPE_E:        # East (mirror)
            pts = [
                px,          py - lift - s,           # top-left
                px + TILE,   py - lift,               # top-right
                px + TILE,   py + TILE - lift,        # bottom-right
                px,          py + TILE - lift - s     # bottom-left
            ]
            self.cv.create_polygon(
                [px, py - lift - s, px, py + TILE - lift - s, px, py + TILE - lift],
                fill="#c07040", outline="#1e1e2e")
            self.cv.create_polygon(
                [px + TILE, py - lift, px + TILE, py + TILE - lift, px + TILE, py + TILE - lift],
                fill="#c07040", outline="#1e1e2e")

        elif t == SLOPE_S:        # South
            pts = [
                px,          py - lift,               # top-left
                px + TILE,   py - lift,               # top-right
                px + TILE,   py + TILE - lift - s,    # bottom-right
                px,          py + TILE - lift - s     # bottom-left
            ]
            # no side triangles

        elif t == SLOPE_N:        # North
            pts = [
                px,          py - lift - s,           # top-left
                px + TILE,   py - lift - s,           # top-right
                px + TILE,   py + TILE - lift,        # bottom-right
                px,          py + TILE - lift         # bottom-left
            ]
            # no side triangles

        else:
            return

        # Main surface
        self.cv.create_polygon(pts, fill="#e0a070", outline="#1e1e2e", width=1)

    def redraw(self):
        self.cv.delete("all")
        max_z = self.view_layer

        for z in range(0, max_z + 1):
            L = self.world.layers[z]
            lift = z * DZ

            for y in range(self.world.h):
                for x in range(self.world.w):
                    t = L["tiles"][y][x]
                    if t is None:
                        continue
                    px = 20 + x * TILE
                    py = 20 + y * TILE

                    if t == BRIDGE:
                        self._draw_bridge(px, py, lift)
                    elif t in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                        # Draw the slope only when we are on the lower of the two layers
                        # (or change the condition to `z == higher` if you prefer the top version)
                        if z == 0 or self.world.tile(x, y, z-1) not in (SLOPE_N, SLOPE_S, SLOPE_E, SLOPE_W):
                            self._draw_slope(px, py, t, lift)
                    else:
                        # normal floor – full supports for its own height
                        self._draw_supports(px, py, lift)
                        col = self._tile_colour(t)
                        self.cv.create_rectangle(px, py - lift,
                                                 px + TILE, py + TILE - lift,
                                                 fill=col, outline="#45475a")

            # walls only for visible layers
            for y in range(self.world.h):
                for x in range(self.world.w + 1):
                    if L["vwalls"][y][x]:
                        self.cv.create_line(20 + x * TILE, 20 + y * TILE - lift,
                                            20 + x * TILE, 20 + (y + 1) * TILE - lift,
                                            fill="#f38ba8", width=3)

            for y in range(self.world.h + 1):
                for x in range(self.world.w):
                    if L["hwalls"][y][x]:
                        yy = 20 + y * TILE - lift
                        self.cv.create_line(20 + x * TILE, yy,
                                            20 + (x + 1) * TILE, yy,
                                            fill="#f38ba8", width=2)
                        # visible south face
                        self.cv.create_rectangle(20 + x * TILE, yy,
                                                 20 + (x + 1) * TILE, yy + SOUTH_WALL_H,
                                                 fill="#c04060", outline="#f38ba8", width=1)

        # robot
        if int(self.robot.z) <= max_z:
            lift = int(self.robot.z) * DZ
            rx = 20 + self.robot.x * TILE
            ry = 20 + self.robot.y * TILE - lift
            size = 16
            pts = []
            for a in (0, 2.4, -2.4):
                pts += [rx + math.cos(self.robot.angle + a) * size,
                        ry + math.sin(self.robot.angle + a) * size]
            self.cv.create_polygon(pts, fill="#89b4fa", outline="#cdd6f4", width=2)
            self.cv.create_text(rx, ry - 24, text=f"z={int(self.robot.z)}",
                                fill="#cdd6f4", font=("Segoe UI", 8))

            for s in self.robot.sensors.values():
                ang = self.robot.angle + s["off"]
                length = s["len"]
                col = "#f38ba8" if s["hit"] else "#a6e3a1"
                self.cv.create_line(rx, ry,
                                    rx + math.cos(ang) * length,
                                    ry + math.sin(ang) * length,
                                    fill=col, width=2)

# ──────────────────────────────────────────────
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robot Mission")
        self.geometry("1020x760")
        self.configure(bg="#11111b")
        self.levels = load_all_levels()
        self.player = load_player()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#11111b")
        style.configure("TLabel", background="#11111b", foreground="#cdd6f4")
        style.configure("TButton", padding=6)
        style.configure("TLabelframe", background="#11111b", foreground="#cdd6f4")
        style.configure("TLabelframe.Label", background="#11111b", foreground="#cdd6f4")

        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.show_menu()

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_menu(self):
        self.clear()
        f = ttk.Frame(self.container)
        f.pack(expand=True)
        ttk.Label(f, text="ROBOT MISSION", font=("Segoe UI", 28, "bold")).pack(pady=28)
        ttk.Button(f, text="Choose Level", width=22,
                   command=self.show_level_select).pack(pady=6)
        ttk.Button(f, text="Watch Solutions", width=22,
                   command=self.show_solutions).pack(pady=6)
        ttk.Button(f, text="Level Editor", width=22,
                   command=self.show_editor_menu).pack(pady=6)
        ttk.Button(f, text="Exit", width=22, command=self.destroy).pack(pady=6)

    def show_editor_menu(self):
        self.clear()
        f = ttk.Frame(self.container)
        f.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        ttk.Label(f, text="Level Editor", font=("Segoe UI", 16, "bold")).pack(pady=10)
        ttk.Button(f, text="＋ New Level", width=22,
                   command=lambda: LevelEditor(self)).pack(pady=6)

        ttk.Label(f, text="Edit existing:", font=("Segoe UI", 11)).pack(pady=(16, 6))
        self.levels = load_all_levels()
        for lv in self.levels:
            path = LEVELS_DIR / lv["_file"]
            ttk.Button(
                f, text=lv.get("name", path.stem), width=28,
                command=lambda p=path, d=lv: LevelEditor(self, level_data=d, level_path=p)
            ).pack(pady=2)

        ttk.Button(f, text="← Back", command=self.show_menu).pack(pady=16)

    def open_level_editor(self):
        # kept for compatibility – opens new level
        LevelEditor(self)

    def show_level_select(self):
        self.clear()
        self.levels = load_all_levels()
        f = ttk.Frame(self.container)
        f.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        ttk.Label(f, text="Select Level", font=("Segoe UI", 16, "bold")).pack(pady=10)
        unlocked = self.player["unlocked"]
        for i, lv in enumerate(self.levels):
            state = "normal" if i < unlocked else "disabled"
            ttk.Button(f, text=lv.get("name", f"Level {i+1}"),
                       command=lambda idx=i: self.show_game(idx),
                       state=state).pack(fill=tk.X, pady=3)
        ttk.Button(f, text="← Back", command=self.show_menu).pack(pady=16)

    def show_solutions(self):
        self.clear()
        self.levels = load_all_levels()
        f = ttk.Frame(self.container)
        f.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        ttk.Label(f, text="Watch Solutions", font=("Segoe UI", 16, "bold")).pack(pady=10)

        any_sol = False
        for i, lv in enumerate(self.levels):
            lid = str(i)
            best = self.player.get("best", {}).get(lid, {})
            algo = best.get("algorithm")
            if not algo:
                continue
            any_sol = True
            t = best.get("time", "?")
            label = f"{lv.get('name', f'Level {i+1}')}  ({t:.2f}s)" if isinstance(t, (int, float)) else lv.get("name", f"Level {i+1}")
            ttk.Button(
                f, text=label,
                command=lambda idx=i, a=algo: self.show_game(
                    idx, solution_mode=True, saved_algorithm=a)
            ).pack(fill=tk.X, pady=3)

        if not any_sol:
            ttk.Label(f, text="No saved solutions yet.\nComplete levels to record them.",
                      foreground="#888").pack(pady=20)

        ttk.Button(f, text="← Back", command=self.show_menu).pack(pady=16)

    def show_game(self, idx, solution_mode=False, saved_algorithm=None):
        self.clear()
        self.levels = load_all_levels()
        GameView(
            self.container, idx, self.levels, self.player,
            on_back=self.show_menu if not solution_mode else self.show_solutions,
            app=self,
            solution_mode=solution_mode,
            saved_algorithm=saved_algorithm
        ).pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    ensure_levels()
    app = MainApp()
    app.mainloop()
