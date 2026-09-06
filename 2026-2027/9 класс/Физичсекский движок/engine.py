import tkinter as tk
from tkinter import ttk, messagebox
import random
import os
import json
import math

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
LOSS_FRAC = 0.10
LOSS_CONST = 4.0
FRICTION_FRAC = 0.10
FRICTION_CONST = 0.08
MAX_SPEED = 14.0
ACCEL = 0.35
EPS = 1e-6

class Rect:
    def __init__(self, canvas, x, y, w, h, color, grounded=False):
        self.canvas = canvas
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.color = color
        self.grounded = grounded
        self.vx = 0.0
        self.vy = 0.0
        self.resting = False
        outline = "#ffdd57" if grounded else "#ffffff"
        width = 3 if grounded else 2
        self.id = canvas.create_rectangle(
            self.x, self.y, self.x + self.w, self.y + self.h,
            fill=color, outline=outline, width=width
        )

    @property
    def volume(self):
        return max(1.0, self.w * self.h)

    @property
    def cx(self):
        return self.x + self.w * 0.5

    @property
    def cy(self):
        return self.y + self.h * 0.5

    def speed(self):
        return math.hypot(self.vx, self.vy)

    def clamp_speed(self, max_speed):
        s = self.speed()
        if s > max_speed and s > EPS:
            f = max_speed / s
            self.vx *= f
            self.vy *= f

    def redraw(self):
        self.canvas.coords(self.id, self.x, self.y, self.x + self.w, self.y + self.h)

    def set_visual(self):
        outline = "#ffdd57" if self.grounded else "#ffffff"
        width = 3 if self.grounded else 2
        self.canvas.itemconfig(self.id, outline=outline, width=width)

    def to_dict(self):
        return {
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "color": self.color, "grounded": self.grounded,
            "vx": self.vx, "vy": self.vy,
        }

    @classmethod
    def from_dict(cls, canvas, d):
        r = cls(canvas, d["x"], d["y"], d["w"], d["h"],
                d.get("color", "#e94560"), d.get("grounded", False))
        r.vx = float(d.get("vx", 0))
        r.vy = float(d.get("vy", 0))
        return r

class RectangleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rectangle Physics (Drag)")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)

        self.rects = []
        self.paused = False
        self.menu_visible = False
        self.dragging = None          # (idx, ox, oy) or ("pan", x, y)

        self.gravity = "none"
        self.accel = ACCEL
        self.max_speed = MAX_SPEED
        self.friction_enabled = True
        self.friction_frac = FRICTION_FRAC
        self.friction_const = FRICTION_CONST

        self.effective_w = 800
        self.effective_h = 600
        self.canvas_w = 1600
        self.canvas_h = 1200
        self.timer_interval = 16
        self.current_dir = os.path.abspath(os.getcwd())

        self.colors = [
            "#e94560", "#0f3460", "#533483", "#16c79a", "#f9a826",
            "#00a8cc", "#f08a5d", "#b83b5e", "#6a2c70", "#08d9d6"
        ]

        # Full-window canvas
        self.canvas = tk.Canvas(self.root, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.config(scrollregion=(0, 0, self.canvas_w, self.canvas_h))

        self.boundary_id = self.canvas.create_rectangle(
            0, 0, self.effective_w, self.effective_h,
            outline="#e94560", width=2, dash=(6, 4)
        )

        # Esc menu: Continue / Load / Exit only
        self.menu_frame = tk.Frame(self.root, bg="#111")
        btn_kw = dict(font=("Segoe UI", 13, "bold"), width=12, height=2,
                      bd=0, relief="flat", cursor="hand2")
        tk.Button(self.menu_frame, text="Continue", bg="#16c79a", fg="white",
                  activebackground="#1dd1a1", command=self.continue_game, **btn_kw).pack(pady=10, padx=30)
        tk.Button(self.menu_frame, text="Load", bg="#0f3460", fg="white",
                  activebackground="#16213e", command=self.open_load_dialog, **btn_kw).pack(pady=10, padx=30)
        tk.Button(self.menu_frame, text="Exit", bg="#533483", fg="white",
                  activebackground="#6a4c93", command=self.root.quit, **btn_kw).pack(pady=10, padx=30)

        self.canvas.bind("<Button-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", self.toggle_menu)
        self.root.bind("<space>", self.toggle_pause)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        self.root.after(80, self._sync_effective)
        self.root.after(self.timer_interval, self.update_loop)

    # ------------------------------------------------------------------
    # Gravity / friction helpers
    # ------------------------------------------------------------------
    def _gravity_vector(self):
        return {
            "N": (0.0, -1.0), "S": (0.0, 1.0),
            "W": (-1.0, 0.0), "E": (1.0, 0.0),
        }.get(self.gravity, (0.0, 0.0))

    def _at_grav_bottom(self, r):
        if self.gravity == "none":
            return False
        gx, gy = self._gravity_vector()
        tol = 1.5
        if gy > 0:
            return r.y + r.h >= self.effective_h - tol
        if gy < 0:
            return r.y <= tol
        if gx > 0:
            return r.x + r.w >= self.effective_w - tol
        if gx < 0:
            return r.x <= tol
        return False

    def _is_support(self, r):
        return r.grounded or r.resting

    def apply_friction(self, r, dist):
        """Perpendicular friction ONLY while on-bottom."""
        if not self.friction_enabled or r.grounded or dist < EPS:
            return
        if not (r.resting or self._at_grav_bottom(r)):
            return
        gx, gy = self._gravity_vector()
        if abs(gx) < EPS and abs(gy) < EPS:
            return
        px, py = -gy, gx
        v_perp = r.vx * px + r.vy * py
        if abs(v_perp) < EPS:
            return
        lost = self.friction_frac * abs(v_perp) + self.friction_const * dist
        new_perp = v_perp - math.copysign(min(lost, abs(v_perp)), v_perp)
        r.vx += (new_perp - v_perp) * px
        r.vy += (new_perp - v_perp) * py

    # ------------------------------------------------------------------
    # Impulse / collision
    # ------------------------------------------------------------------
    @staticmethod
    def _overlap(a, b):
        ox = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
        oy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
        return ox, oy

    def _bounce_off_static(self, body, nx, ny, soft=False):
        if body.grounded:
            return
        vn = body.vx * nx + body.vy * ny
        if vn >= 0:
            return
        if soft and abs(vn) <= self.accel * 2.5:
            body.vx -= vn * nx
            body.vy -= vn * ny
            return
        I = body.volume * vn
        lost = LOSS_FRAC * abs(I) + LOSS_CONST
        I_rest = -math.copysign(max(0.0, abs(I) - lost), I)
        new_vn = I_rest / body.volume
        body.vx += (new_vn - vn) * nx
        body.vy += (new_vn - vn) * ny
        body.clamp_speed(self.max_speed)
        body.resting = False

    def _apply_impulse_pair(self, a, b, nx, ny):
        a_sup, b_sup = self._is_support(a), self._is_support(b)
        if a_sup and b_sup:
            return
        if a_sup and not b_sup:
            self._bounce_off_static(b, -nx, -ny, soft=True)
            return
        if b_sup and not a_sup:
            self._bounce_off_static(a, nx, ny, soft=True)
            return

        va = a.vx * nx + a.vy * ny
        vb = b.vx * nx + b.vy * ny
        if vb - va > 0:
            return

        ma, mb = a.volume, b.volume
        Ia, Ib = ma * va, mb * vb
        if abs(Ia) >= abs(Ib):
            Il, Is, ml, ms, large_is_a = Ia, Ib, ma, mb, True
        else:
            Il, Is, ml, ms, large_is_a = Ib, Ia, mb, ma, False

        lost = LOSS_FRAC * abs(Il) + LOSS_CONST
        Il_after = Il - math.copysign(min(lost, abs(Il)), Il)
        preserved = 0.5 * Il
        pool = Il_after - preserved
        if pool * Il < 0:
            pool = 0.0
        share = pool * (ms / (ml + ms))
        keep = pool - share
        new_Il = preserved + Is
        new_Is = share + keep

        def set_n(body, new_I, m):
            old = body.vx * nx + body.vy * ny
            body.vx += (new_I / m - old) * nx
            body.vy += (new_I / m - old) * ny

        if large_is_a:
            set_n(a, new_Il, ma)
            set_n(b, new_Is, mb)
        else:
            set_n(b, new_Il, mb)
            set_n(a, new_Is, ma)
        a.clamp_speed(self.max_speed)
        b.clamp_speed(self.max_speed)
        a.resting = b.resting = False

    def _positional_separate(self, a, b):
        ox, oy = self._overlap(a, b)
        if ox <= 0 or oy <= 0:
            return
        if ox < oy:
            nx = 1.0 if a.cx < b.cx else -1.0
            if self._is_support(a) and not self._is_support(b):
                b.x += nx * ox
            elif self._is_support(b) and not self._is_support(a):
                a.x -= nx * ox
            elif not self._is_support(a) and not self._is_support(b):
                a.x -= nx * ox * 0.5
                b.x += nx * ox * 0.5
        else:
            ny = 1.0 if a.cy < b.cy else -1.0
            if self._is_support(a) and not self._is_support(b):
                b.y += ny * oy
            elif self._is_support(b) and not self._is_support(a):
                a.y -= ny * oy
            elif not self._is_support(a) and not self._is_support(b):
                a.y -= ny * oy * 0.5
                b.y += ny * oy * 0.5
        self.clamp_rect(a)
        self.clamp_rect(b)

    def _handle_walls(self, r):
        if r.grounded:
            self.clamp_rect(r)
            r.vx = r.vy = 0.0
            return
        gx, gy = self._gravity_vector()
        on_bottom = self._at_grav_bottom(r)

        for hit, nx, ny, toward_floor in (
            (r.x < 0, -1.0, 0.0, gx < 0),
            (r.x + r.w > self.effective_w, 1.0, 0.0, gx > 0),
            (r.y < 0, 0.0, -1.0, gy < 0),
            (r.y + r.h > self.effective_h, 0.0, 1.0, gy > 0),
        ):
            if not hit:
                continue
            if on_bottom and toward_floor:
                vn = r.vx * nx + r.vy * ny
                if vn <= self.accel * 2.5:
                    if abs(nx) > 0:
                        r.vx = 0.0
                    if abs(ny) > 0:
                        r.vy = 0.0
                    r.resting = True
                    self.clamp_rect(r)
                    continue
            self._bounce_off_static(r, nx, ny, soft=False)
            self.clamp_rect(r)
        self.clamp_rect(r)

    def clamp_rect(self, r):
        r.x = max(0.0, min(r.x, self.effective_w - r.w))
        r.y = max(0.0, min(r.y, self.effective_h - r.h))

    # ------------------------------------------------------------------
    # Integration
    # ------------------------------------------------------------------
    def apply_gravity_accel(self):
        if self.gravity == "none":
            return
        gx, gy = self._gravity_vector()
        ax, ay = gx * self.accel, gy * self.accel
        for i, r in enumerate(self.rects):
            if r.grounded:
                r.vx = r.vy = 0.0
                continue
            if self.dragging and self.dragging[0] == i:
                continue
            if r.resting and self._at_grav_bottom(r):
                if abs(gy) > 0:
                    r.vy = 0.0
                if abs(gx) > 0:
                    r.vx = 0.0
                continue
            r.resting = False
            r.vx += ax
            r.vy += ay
            r.clamp_speed(self.max_speed)

    def integrate(self):
        for i, r in enumerate(self.rects):
            if r.grounded:
                continue
            if self.dragging and self.dragging[0] == i:
                continue
            old_x, old_y = r.x, r.y
            r.x += r.vx
            r.y += r.vy
            dist = math.hypot(r.x - old_x, r.y - old_y)
            self._handle_walls(r)
            if self._at_grav_bottom(r):
                gx, gy = self._gravity_vector()
                toward = r.vx * gx + r.vy * gy
                if toward <= self.accel * 2.5:
                    if abs(gy) > 0:
                        r.vy = 0.0
                    if abs(gx) > 0:
                        r.vx = 0.0
                    r.resting = True
            if r.resting or self._at_grav_bottom(r):
                self.apply_friction(r, dist)
            r.redraw()

    def resolve_collisions(self):
        n = len(self.rects)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = self.rects[i], self.rects[j]
                ox, oy = self._overlap(a, b)
                if ox <= 0 or oy <= 0:
                    continue
                self._positional_separate(a, b)
                if ox < oy:
                    nx, ny = (1.0 if a.cx < b.cx else -1.0), 0.0
                else:
                    nx, ny = 0.0, (1.0 if a.cy < b.cy else -1.0)
                self._apply_impulse_pair(a, b, nx, ny)
                a.redraw()
                b.redraw()

    # ------------------------------------------------------------------
    # Drag rectangle or pan canvas
    # ------------------------------------------------------------------
    def try_drag_move(self, primary, dx, dy):
        if abs(dx) < EPS and abs(dy) < EPS:
            return
        self._drag_push(primary, dx, dy, set())
        dist = math.hypot(dx, dy)
        if dist > EPS:
            speed = min(dist, self.max_speed)
            primary.vx = (dx / dist) * speed
            primary.vy = (dy / dist) * speed
        else:
            primary.vx = primary.vy = 0.0
        primary.resting = False
        primary.clamp_speed(self.max_speed)
        for r in self.rects:
            r.redraw()

    def _drag_push(self, primary, dx, dy, visited):
        if id(primary) in visited:
            return
        visited.add(id(primary))
        old_x, old_y = primary.x, primary.y
        primary.x += dx
        primary.y += dy
        self.clamp_rect(primary)
        adx, ady = primary.x - old_x, primary.y - old_y
        if abs(adx) < EPS and abs(ady) < EPS:
            return

        for other in self.rects:
            if other is primary:
                continue
            ox, oy = self._overlap(primary, other)
            if ox <= 0 or oy <= 0:
                continue
            if abs(adx) >= abs(ady) and abs(adx) > EPS:
                if adx > 0:
                    pen = (primary.x + primary.w) - other.x
                    if pen <= 0:
                        continue
                    if self._is_support(other) and not primary.grounded:
                        primary.x -= pen
                    elif not self._is_support(other):
                        self._drag_push(other, pen, 0, visited)
                        ox2, _ = self._overlap(primary, other)
                        if ox2 > 0:
                            primary.x -= ox2
                else:
                    pen = (other.x + other.w) - primary.x
                    if pen <= 0:
                        continue
                    if self._is_support(other) and not primary.grounded:
                        primary.x += pen
                    elif not self._is_support(other):
                        self._drag_push(other, -pen, 0, visited)
                        ox2, _ = self._overlap(primary, other)
                        if ox2 > 0:
                            primary.x += ox2
            else:
                if ady > 0:
                    pen = (primary.y + primary.h) - other.y
                    if pen <= 0:
                        continue
                    if self._is_support(other) and not primary.grounded:
                        primary.y -= pen
                    elif not self._is_support(other):
                        self._drag_push(other, 0, pen, visited)
                        _, oy2 = self._overlap(primary, other)
                        if oy2 > 0:
                            primary.y -= oy2
                elif ady < 0:
                    pen = (other.y + other.h) - primary.y
                    if pen <= 0:
                        continue
                    if self._is_support(other) and not primary.grounded:
                        primary.y += pen
                    elif not self._is_support(other):
                        self._drag_push(other, 0, -pen, visited)
                        _, oy2 = self._overlap(primary, other)
                        if oy2 > 0:
                            primary.y += oy2

            if not self._is_support(other) and not other.grounded:
                d = math.hypot(adx, ady)
                if d > EPS:
                    sp = min(d, self.max_speed)
                    other.vx = (adx / d) * sp
                    other.vy = (ady / d) * sp
                    other.resting = False
                    other.clamp_speed(self.max_speed)
        self.clamp_rect(primary)

    # ------------------------------------------------------------------
    # Load dialog
    # ------------------------------------------------------------------
    def open_load_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Load Configuration")
        win.geometry("480x420")
        win.transient(self.root)
        win.grab_set()

        path_var = tk.StringVar(value=self.current_dir)
        tk.Label(win, textvariable=path_var, bg="#1a1a2e", fg="#ccc",
                 font=("Consolas", 9), anchor="w").pack(fill=tk.X, padx=6, pady=6)

        list_box = tk.Frame(win)
        list_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cv = tk.Canvas(list_box, bg="#16213e", highlightthickness=0)
        sb = ttk.Scrollbar(list_box, orient=tk.VERTICAL, command=cv.yview)
        flist = tk.Frame(cv, bg="#16213e")
        flist.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=flist, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def on_wheel(event):
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")
        cv.bind_all("<MouseWheel>", on_wheel)

        name_var = tk.StringVar()
        ef = tk.Frame(win)
        ef.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(ef, text="File:").pack(side=tk.LEFT)
        tk.Entry(ef, textvariable=name_var, font=("Segoe UI", 10)).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        def populate():
            for w in flist.winfo_children():
                w.destroy()
            path_var.set(self.current_dir)
            try:
                entries = os.listdir(self.current_dir)
            except PermissionError:
                tk.Label(flist, text="(Permission denied)", bg="#16213e",
                         fg="#e94560").pack(anchor="w", padx=8, pady=4)
                return
            dirs, files = [], []
            for n in entries:
                (dirs if os.path.isdir(os.path.join(self.current_dir, n)) else files).append(n)
            dirs.sort(key=str.lower)
            files.sort(key=str.lower)
            parent = os.path.abspath(os.path.join(self.current_dir, ".."))
            items = []
            if parent != self.current_dir:
                items.append(("..", True))
            items += [(d, True) for d in dirs] + [(f, False) for f in files]
            for name, is_dir in items:
                bg = "#0f3460" if is_dir else "#1a1a2e"
                fg = "#f9a826" if is_dir else "#eee"
                lbl = tk.Label(flist, text=("📁 " if is_dir else "📄 ") + name,
                               bg=bg, fg=fg, font=("Segoe UI", 10),
                               anchor="w", padx=10, pady=4, cursor="hand2")
                lbl.pack(fill=tk.X, padx=2, pady=1)
                lbl.bind("<Enter>", lambda e, w=lbl, d=is_dir: w.config(
                    bg="#e94560" if not d else "#533483"))
                lbl.bind("<Leave>", lambda e, w=lbl, b=bg: w.config(bg=b))
                if is_dir:
                    def go(n=name):
                        np = os.path.abspath(os.path.join(self.current_dir, n))
                        if os.path.isdir(np):
                            self.current_dir = np
                            populate()
                    lbl.bind("<Button-1>", lambda e, g=go: g())
                else:
                    lbl.bind("<Button-1>", lambda e, n=name: name_var.set(n))
                    def load_file(n=name):
                        name_var.set(n)
                        full = os.path.abspath(os.path.join(self.current_dir, n))
                        try:
                            self._load_from_file(full)
                            cv.unbind_all("<MouseWheel>")
                            win.destroy()
                            self.continue_game()
                        except Exception as ex:
                            messagebox.showerror("Error", str(ex), parent=win)
                    lbl.bind("<Double-Button-1>", lambda e, lf=load_file: lf())

        def do_load():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Name required", "Select a file.", parent=win)
                return
            if not name.lower().endswith(".json"):
                name += ".json"
            full = os.path.abspath(os.path.join(self.current_dir, name))
            if not os.path.isfile(full):
                messagebox.showwarning("Not found", full, parent=win)
                return
            try:
                self._load_from_file(full)
                cv.unbind_all("<MouseWheel>")
                win.destroy()
                self.continue_game()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def do_cancel():
            cv.unbind_all("<MouseWheel>")
            win.destroy()

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=6, pady=8)
        tk.Button(bf, text="Refresh", command=populate, width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Cancel", command=do_cancel, width=10).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text="Load", command=do_load, bg="#16c79a", fg="white",
                  width=10).pack(side=tk.RIGHT, padx=4)
        populate()

    def _load_from_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in self.rects:
            self.canvas.delete(r.id)
        self.rects.clear()
        self.dragging = None

        self.effective_w = int(data.get("effective_w", self.effective_w))
        self.effective_h = int(data.get("effective_h", self.effective_h))
        self.gravity = data.get("gravity", "none")
        self.accel = float(data.get("accel", ACCEL))
        self.max_speed = float(data.get("max_speed", MAX_SPEED))
        self.friction_enabled = bool(data.get("friction_enabled", True))
        self.friction_frac = float(data.get("friction_frac", FRICTION_FRAC))
        self.friction_const = float(data.get("friction_const", FRICTION_CONST))
        self.canvas.coords(self.boundary_id, 0, 0, self.effective_w, self.effective_h)
        for item in data.get("rectangles", []):
            self.rects.append(Rect.from_dict(self.canvas, item))

    # ------------------------------------------------------------------
    # Input – always drag mode; empty space pans canvas
    # ------------------------------------------------------------------
    def find_rect_at(self, x, y):
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        for i in range(len(self.rects) - 1, -1, -1):
            r = self.rects[i]
            if r.x <= cx <= r.x + r.w and r.y <= cy <= r.y + r.h:
                return i
        return None

    def on_left_press(self, event):
        if self.menu_visible:
            return
        x, y = event.x, event.y
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        idx = self.find_rect_at(x, y)
        if idx is not None:
            r = self.rects[idx]
            self.dragging = (idx, cx - r.x, cy - r.y)
            self.canvas.tag_raise(r.id)
            r.vx = r.vy = 0.0
            r.resting = False
        else:
            # no rectangle under cursor → pan canvas
            self.dragging = ("pan", x, y)
            self.canvas.scan_mark(x, y)

    def on_drag(self, event):
        if self.dragging is None or self.menu_visible:
            return
        if self.dragging[0] == "pan":
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            return
        idx, ox, oy = self.dragging
        r = self.rects[idx]
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        dx = (cx - ox) - r.x
        dy = (cy - oy) - r.y
        self.try_drag_move(r, dx, dy)

    def on_release(self, event):
        if self.dragging and self.dragging[0] != "pan":
            r = self.rects[self.dragging[0]]
            r.clamp_speed(self.max_speed)
            if r.grounded:
                r.vx = r.vy = 0.0
        self.dragging = None

    # ------------------------------------------------------------------
    # Menu / pause
    # ------------------------------------------------------------------
    def toggle_menu(self, event=None):
        if self.menu_visible:
            self.continue_game()
        else:
            self.paused = True
            self.menu_visible = True
            self.menu_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.menu_frame.lift()

    def continue_game(self):
        self.paused = False
        self.menu_visible = False
        self.menu_frame.place_forget()

    def toggle_pause(self, event=None):
        if self.menu_visible:
            return
        self.paused = not self.paused

    # ------------------------------------------------------------------
    # Loop / resize
    # ------------------------------------------------------------------
    def update_loop(self):
        if not self.paused:
            self.apply_gravity_accel()
            self.integrate()
            self.resolve_collisions()
        self.root.after(self.timer_interval, self.update_loop)

    def on_canvas_configure(self, event):
        pass

    def _sync_effective(self):
        # keep boundary; effective size comes from loaded file or defaults
        self.canvas.coords(self.boundary_id, 0, 0, self.effective_w, self.effective_h)

if __name__ == "__main__":
    root = tk.Tk()
    app = RectangleApp(root)
    root.mainloop()
