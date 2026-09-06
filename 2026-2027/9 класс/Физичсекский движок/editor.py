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
FRICTION_CONST = 0.08          # per distance-unit (pixels this frame)
MAX_SPEED_DEFAULT = 14.0
ACCEL_DEFAULT = 0.35
EPS = 1e-6

class Rect:
    """Axis-aligned rectangle with volume (area) and velocity."""

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

    def set_grounded_visual(self):
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
        self.root.title("Rectangle Physics Canvas")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        self.rects = []
        self.current_tool = "arrow"
        self.selected_idx = None
        self.gravity = "none"
        self.paused = False
        self.menu_visible = False
        self.dragging = None
        self.timer_interval = 16

        self.accel = ACCEL_DEFAULT
        self.max_speed = MAX_SPEED_DEFAULT
        self.friction_frac = FRICTION_FRAC
        self.friction_const = FRICTION_CONST
        self.friction_enabled = True

        self.effective_w = 800
        self.effective_h = 600
        self.canvas_w = 1600
        self.canvas_h = 1200

        self.colors = [
            "#e94560", "#0f3460", "#533483", "#16c79a", "#f9a826",
            "#00a8cc", "#f08a5d", "#b83b5e", "#6a2c70", "#08d9d6"
        ]
        self.current_dir = os.path.abspath(os.getcwd())

        # ---------- Layout ----------
        self.main = tk.Frame(self.root, bg="#16213e")
        self.main.pack(fill=tk.BOTH, expand=True)

        self.left_pane = ttk.Panedwindow(self.main, orient=tk.VERTICAL)
        self.left_pane.pack(side=tk.LEFT, fill=tk.Y)

        self.tool_frame = tk.Frame(self.left_pane, bg="#0f3460", width=220)
        self.left_pane.add(self.tool_frame, weight=0)

        tk.Label(self.tool_frame, text="Tools", bg="#0f3460", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(pady=(10, 6))

        self.tool_btns = {}
        for key, label in [
            ("arrow", "Arrow (Drag)"),
            ("add", "Add Rectangle"),
            ("select", "Select"),
            ("physics", "Physics"),
            ("canvas", "Canvas"),
        ]:
            b = tk.Button(
                self.tool_frame, text=label, anchor="w",
                bg="#1a1a2e", fg="white", activebackground="#e94560",
                activeforeground="white", bd=0, relief="flat",
                font=("Segoe UI", 10), padx=12, pady=6,
                command=lambda k=key: self.set_tool(k)
            )
            b.pack(fill=tk.X, padx=8, pady=2)
            self.tool_btns[key] = b

        self.opt_container = tk.Frame(self.left_pane, bg="#0f3460", width=220)
        self.left_pane.add(self.opt_container, weight=3)

        self.opt_title = tk.Label(
            self.opt_container, text="", bg="#0f3460", fg="white",
            font=("Segoe UI", 11, "bold")
        )
        self.opt_title.pack(pady=(12, 6))

        self.opt_body = tk.Frame(self.opt_container, bg="#0f3460")
        self.opt_body.pack(fill=tk.BOTH, expand=True, padx=6)

        self.canvas = tk.Canvas(self.main, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.config(scrollregion=(0, 0, self.canvas_w, self.canvas_h))

        self.boundary_id = self.canvas.create_rectangle(
            0, 0, self.effective_w, self.effective_h,
            outline="#e94560", width=2, dash=(6, 4)
        )

        # Overlay menu
        self.menu_frame = tk.Frame(self.root, bg="#111")
        btn_kw = dict(font=("Segoe UI", 13, "bold"), width=12, height=2,
                      bd=0, relief="flat", cursor="hand2")
        for text, bg, abg, cmd in [
            ("Reset", "#e94560", "#ff6b81", self.reset),
            ("Save As", "#0f3460", "#16213e", self.open_save_dialog),
            ("Load", "#0f3460", "#16213e", self.open_load_dialog),
            ("Continue", "#16c79a", "#1dd1a1", self.continue_game),
            ("Exit", "#533483", "#6a4c93", self.root.quit),
        ]:
            tk.Button(self.menu_frame, text=text, bg=bg, fg="white",
                      activebackground=abg, command=cmd, **btn_kw).pack(pady=8, padx=30)

        self.canvas.bind("<Button-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Escape>", self.toggle_menu)
        self.root.bind("<space>", self.toggle_pause)

        self._build_add_options()
        self._build_select_options()
        self._build_physics_options()
        self._build_canvas_options()
        self._build_arrow_options()

        self.set_tool("arrow")
        self.root.after(80, self._sync_effective)
        self.root.after(self.timer_interval, self.update_loop)

    # ==================================================================
    # Gravity / friction helpers
    # ==================================================================
    def _gravity_vector(self):
        if self.gravity == "N":
            return 0.0, -1.0
        if self.gravity == "S":
            return 0.0, 1.0
        if self.gravity == "W":
            return -1.0, 0.0
        if self.gravity == "E":
            return 1.0, 0.0
        return 0.0, 0.0

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
        """Static or resting-on-bottom body that can support free objects."""
        return r.grounded or r.resting

    def apply_friction(self, r, dist):
        """
    Friction on the component perpendicular to gravity.
    Applied ONLY when the object is in on-bottom (resting) state.
    Loss ≈ friction_frac * |v_perp| + friction_const * distance  (per tick).
        """
        if not self.friction_enabled or r.grounded or dist < EPS:
            return
    # Friction only while sitting on the gravitational bottom
        if not (r.resting or self._at_grav_bottom(r)):
            return

        gx, gy = self._gravity_vector()

        if abs(gx) < EPS and abs(gy) < EPS:
        # no gravity direction → nothing to be "on-bottom" against
            return

    # perpendicular unit vector
        px, py = -gy, gx
        v_perp = r.vx * px + r.vy * py
        if abs(v_perp) < EPS:
            return
        lost = self.friction_frac * abs(v_perp) + self.friction_const * dist
        new_perp = v_perp - math.copysign(min(lost, abs(v_perp)), v_perp)
        r.vx += (new_perp - v_perp) * px
        r.vy += (new_perp - v_perp) * py

    # ==================================================================
    # Impulse helpers
    # ==================================================================
    @staticmethod
    def _overlap(a, b):
        ox = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
        oy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
        return ox, oy

    def _bounce_off_static(self, body, nx, ny, soft=False):
        """
        Collision with static / resting support.
        soft=True (grav-bottom rules): absorb small gravitational contact;
        only bounce when a meaningful impulse is directed into the support.
        """
        if body.grounded:
            return
        vn = body.vx * nx + body.vy * ny
        if vn >= 0:
            return
        if soft and abs(vn) <= self.accel * 2.5:
            # absorb – zero normal component only
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
        """
        nx,ny = unit normal from a toward b.
        Support bodies (grounded / resting) use grav-bottom rules vs free bodies.
        """
        a_sup = self._is_support(a)
        b_sup = self._is_support(b)

        if a_sup and b_sup:
            return

        if a_sup and not b_sup:
            self._bounce_off_static(b, -nx, -ny, soft=True)
            return
        if b_sup and not a_sup:
            self._bounce_off_static(a, nx, ny, soft=True)
            return

        # both free
        va = a.vx * nx + a.vy * ny
        vb = b.vx * nx + b.vy * ny
        if vb - va > 0:
            return

        ma, mb = a.volume, b.volume
        Ia, Ib = ma * va, mb * vb

        if abs(Ia) >= abs(Ib):
            Il, Is = Ia, Ib
            ml, ms = ma, mb
            large_is_a = True
        else:
            Il, Is = Ib, Ia
            ml, ms = mb, ma
            large_is_a = False

        lost = LOSS_FRAC * abs(Il) + LOSS_CONST
        Il_after_loss = Il - math.copysign(min(lost, abs(Il)), Il)
        preserved = 0.5 * Il
        pool = Il_after_loss - preserved
        if pool * Il < 0:
            pool = 0.0

        total_m = ml + ms
        share = pool * (ms / total_m)
        keep_from_pool = pool - share
        new_Il = preserved + Is
        new_Is = share + keep_from_pool

        def set_normal_vel(body, new_I, m):
            old_n = body.vx * nx + body.vy * ny
            new_n = new_I / m
            body.vx += (new_n - old_n) * nx
            body.vy += (new_n - old_n) * ny

        if large_is_a:
            set_normal_vel(a, new_Il, ma)
            set_normal_vel(b, new_Is, mb)
        else:
            set_normal_vel(b, new_Il, mb)
            set_normal_vel(a, new_Is, ma)

        a.clamp_speed(self.max_speed)
        b.clamp_speed(self.max_speed)
        a.resting = False
        b.resting = False

    def _positional_separate(self, a, b):
        ox, oy = self._overlap(a, b)
        if ox <= 0 or oy <= 0:
            return None, None

        if ox < oy:
            nx = 1.0 if a.cx < b.cx else -1.0
            ny = 0.0
            if self._is_support(a) and not self._is_support(b):
                b.x += nx * ox
            elif self._is_support(b) and not self._is_support(a):
                a.x -= nx * ox
            elif not self._is_support(a) and not self._is_support(b):
                a.x -= nx * ox * 0.5
                b.x += nx * ox * 0.5
            else:
                return None, None
        else:
            nx = 0.0
            ny = 1.0 if a.cy < b.cy else -1.0
            if self._is_support(a) and not self._is_support(b):
                b.y += ny * oy
            elif self._is_support(b) and not self._is_support(a):
                a.y -= ny * oy
            elif not self._is_support(a) and not self._is_support(b):
                a.y -= ny * oy * 0.5
                b.y += ny * oy * 0.5
            else:
                return None, None
        self.clamp_rect(a)
        self.clamp_rect(b)
        return nx, ny

    # ==================================================================
    # Walls
    # ==================================================================
    def _handle_walls(self, r):
        if r.grounded:
            self.clamp_rect(r)
            r.vx = r.vy = 0.0
            return

        gx, gy = self._gravity_vector()
        on_bottom = self._at_grav_bottom(r)

        hit_left = r.x < 0
        hit_right = r.x + r.w > self.effective_w
        if hit_left or hit_right:
            nx = -1.0 if hit_left else 1.0
            if on_bottom and abs(gx) > 0 and (
                (gx < 0 and hit_left) or (gx > 0 and hit_right)
            ):
                vn = r.vx * nx
                if vn <= self.accel * 2.5:
                    r.vx = 0.0
                    r.resting = True
                    self.clamp_rect(r)
                else:
                    self._bounce_off_static(r, nx, 0.0, soft=False)
                    self.clamp_rect(r)
            else:
                self._bounce_off_static(r, nx, 0.0, soft=False)
                self.clamp_rect(r)

        hit_top = r.y < 0
        hit_bot = r.y + r.h > self.effective_h
        if hit_top or hit_bot:
            ny = -1.0 if hit_top else 1.0
            if on_bottom and abs(gy) > 0 and (
                (gy < 0 and hit_top) or (gy > 0 and hit_bot)
            ):
                vn = r.vy * ny
                if vn <= self.accel * 2.5:
                    r.vy = 0.0
                    r.resting = True
                    self.clamp_rect(r)
                else:
                    self._bounce_off_static(r, 0.0, ny, soft=False)
                    self.clamp_rect(r)
            else:
                self._bounce_off_static(r, 0.0, ny, soft=False)
                self.clamp_rect(r)

        self.clamp_rect(r)

    def clamp_rect(self, r):
        r.x = max(0.0, min(r.x, self.effective_w - r.w))
        r.y = max(0.0, min(r.y, self.effective_h - r.h))

    # ==================================================================
    # Integration
    # ==================================================================
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
            # update resting flag first
            if self._at_grav_bottom(r):
                gx, gy = self._gravity_vector()
                toward = r.vx * gx + r.vy * gy
                if toward <= self.accel * 2.5:
                    if abs(gy) > 0:
                        r.vy = 0.0
                    if abs(gx) > 0:
                        r.vx = 0.0
                    r.resting = True
            # friction only for on-bottom bodies
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
                if abs(ox) <= abs(oy) if False else ox < oy:
                    nx = 1.0 if a.cx < b.cx else -1.0
                    ny = 0.0
                else:
                    nx = 0.0
                    ny = 1.0 if a.cy < b.cy else -1.0
                # after separate, re-evaluate normal from centres
                if ox < oy:
                    nx = 1.0 if a.cx < b.cx else -1.0
                    ny = 0.0
                else:
                    nx = 0.0
                    ny = 1.0 if a.cy < b.cy else -1.0
                self._apply_impulse_pair(a, b, nx, ny)
                a.redraw()
                b.redraw()

    # ==================================================================
    # Drag – full 2D velocity from tick movement
    # ==================================================================
    def try_drag_move(self, primary, dx, dy):
        if abs(dx) < EPS and abs(dy) < EPS:
            return
        self._drag_axis(primary, dx, dy, set())

        # Velocity = direction of this tick's movement, magnitude =
        # min(movement length this tick, max_speed)
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

    def _drag_axis(self, primary, dx, dy, visited):
        if id(primary) in visited:
            return
        visited.add(id(primary))

        old_x, old_y = primary.x, primary.y
        primary.x += dx
        primary.y += dy
        self.clamp_rect(primary)
        adx = primary.x - old_x
        ady = primary.y - old_y
        if abs(adx) < EPS and abs(ady) < EPS:
            return

        for other in self.rects:
            if other is primary:
                continue
            ox, oy = self._overlap(primary, other)
            if ox <= 0 or oy <= 0:
                continue

            # Push free bodies; supports block
            if abs(adx) >= abs(ady) and abs(adx) > EPS:
                if adx > 0:
                    pen = (primary.x + primary.w) - other.x
                    if pen <= 0:
                        continue
                    if self._is_support(other) and not primary.grounded:
                        primary.x -= pen
                    elif not self._is_support(other):
                        self._drag_axis(other, pen, 0, visited)
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
                        self._drag_axis(other, -pen, 0, visited)
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
                        self._drag_axis(other, 0, pen, visited)
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
                        self._drag_axis(other, 0, -pen, visited)
                        _, oy2 = self._overlap(primary, other)
                        if oy2 > 0:
                            primary.y += oy2

            # Propagate a fraction of drag velocity to pushed free bodies
            if not self._is_support(other) and not other.grounded:
                dist = math.hypot(adx, ady)
                if dist > EPS:
                    speed = min(dist, self.max_speed)
                    other.vx = (adx / dist) * speed
                    other.vy = (ady / dist) * speed
                    other.resting = False
                    other.clamp_speed(self.max_speed)

        self.clamp_rect(primary)

    # ==================================================================
    # File I/O
    # ==================================================================
    def _make_file_browser(self, title, mode="load"):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("480x420")
        win.transient(self.root)
        win.grab_set()

        path_frame = tk.Frame(win, bg="#1a1a2e")
        path_frame.pack(fill=tk.X, padx=6, pady=6)
        self._fb_path_var = tk.StringVar(value=self.current_dir)
        tk.Label(path_frame, textvariable=self._fb_path_var, bg="#1a1a2e",
                 fg="#ccc", font=("Consolas", 9), anchor="w").pack(fill=tk.X, padx=4)

        list_container = tk.Frame(win)
        list_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        canvas = tk.Canvas(list_container, bg="#16213e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        self._fb_list = tk.Frame(canvas, bg="#16213e")
        self._fb_list.bind("<Configure>",
                           lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._fb_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        entry_frame = tk.Frame(win)
        entry_frame.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(entry_frame, text="File:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._fb_name_var = tk.StringVar()
        tk.Entry(entry_frame, textvariable=self._fb_name_var,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=6, pady=8)

        def do_cancel():
            canvas.unbind_all("<MouseWheel>")
            win.destroy()

        def do_action():
            name = self._fb_name_var.get().strip()
            if not name:
                messagebox.showwarning("Name required", "Enter or select a file name.", parent=win)
                return
            if not name.lower().endswith(".json"):
                name += ".json"
            full = os.path.abspath(os.path.join(self.current_dir, name))
            if mode == "save":
                try:
                    self._save_to_file(full)
                    messagebox.showinfo("Saved", f"Saved to:\n{full}", parent=win)
                    do_cancel()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=win)
            else:
                if not os.path.isfile(full):
                    messagebox.showwarning("Not found", f"Missing:\n{full}", parent=win)
                    return
                try:
                    self._load_from_file(full)
                    do_cancel()
                    self.continue_game()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=win)

        tk.Button(btn_frame, text="Refresh",
                  command=lambda: self._populate_file_list(mode), width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Cancel", command=do_cancel, width=10).pack(side=tk.RIGHT, padx=4)
        tk.Button(btn_frame, text=("Save" if mode == "save" else "Load"),
                  command=do_action, bg="#16c79a", fg="white", width=10).pack(side=tk.RIGHT, padx=4)

        self._fb_win = win
        self._fb_canvas = canvas
        self._populate_file_list(mode)

    def _populate_file_list(self, mode):
        for w in self._fb_list.winfo_children():
            w.destroy()
        self._fb_path_var.set(self.current_dir)
        try:
            entries = os.listdir(self.current_dir)
        except PermissionError:
            tk.Label(self._fb_list, text="(Permission denied)", bg="#16213e",
                     fg="#e94560").pack(anchor="w", padx=8, pady=4)
            return
        dirs, files = [], []
        for name in entries:
            full = os.path.join(self.current_dir, name)
            (dirs if os.path.isdir(full) else files).append(name)
        dirs.sort(key=str.lower)
        files.sort(key=str.lower)
        parent = os.path.abspath(os.path.join(self.current_dir, ".."))
        if parent != self.current_dir:
            self._add_fb_item("..", True, mode)
        for d in dirs:
            self._add_fb_item(d, True, mode)
        for f in files:
            self._add_fb_item(f, False, mode)

    def _add_fb_item(self, name, is_dir, mode):
        bg = "#0f3460" if is_dir else "#1a1a2e"
        fg = "#f9a826" if is_dir else "#eeeeee"
        lbl = tk.Label(self._fb_list, text=("📁 " if is_dir else "📄 ") + name,
                       bg=bg, fg=fg, font=("Segoe UI", 10), anchor="w",
                       padx=10, pady=4, cursor="hand2")
        lbl.pack(fill=tk.X, padx=2, pady=1)
        lbl.bind("<Enter>", lambda e, w=lbl, d=is_dir: w.config(bg="#e94560" if not d else "#533483"))
        lbl.bind("<Leave>", lambda e, w=lbl, b=bg: w.config(bg=b))
        if is_dir:
            def go(n=name):
                np = os.path.abspath(os.path.join(self.current_dir, n))
                if os.path.isdir(np):
                    self.current_dir = np
                    self._populate_file_list(mode)
            lbl.bind("<Button-1>", lambda e: go())
        else:
            lbl.bind("<Button-1>", lambda e, n=name: self._fb_name_var.set(n))
            if mode == "load":
                def load(n=name):
                    self._fb_name_var.set(n)
                    full = os.path.abspath(os.path.join(self.current_dir, n))
                    try:
                        self._load_from_file(full)
                        self._fb_canvas.unbind_all("<MouseWheel>")
                        self._fb_win.destroy()
                        self.continue_game()
                    except Exception as ex:
                        messagebox.showerror("Error", str(ex), parent=self._fb_win)
                lbl.bind("<Double-Button-1>", lambda e: load())

    def _save_to_file(self, path):
        data = {
            "version": 3,
            "effective_w": self.effective_w,
            "effective_h": self.effective_h,
            "gravity": self.gravity,
            "accel": self.accel,
            "max_speed": self.max_speed,
            "friction_enabled": self.friction_enabled,
            "friction_frac": self.friction_frac,
            "friction_const": self.friction_const,
            "rectangles": [r.to_dict() for r in self.rects],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_from_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in self.rects:
            self.canvas.delete(r.id)
        self.rects.clear()
        self.selected_idx = None
        self.dragging = None

        self.effective_w = int(data.get("effective_w", self.effective_w))
        self.effective_h = int(data.get("effective_h", self.effective_h))
        self.gravity = data.get("gravity", "none")
        self.accel = float(data.get("accel", ACCEL_DEFAULT))
        self.max_speed = float(data.get("max_speed", MAX_SPEED_DEFAULT))
        self.friction_enabled = bool(data.get("friction_enabled", True))
        self.friction_frac = float(data.get("friction_frac", FRICTION_FRAC))
        self.friction_const = float(data.get("friction_const", FRICTION_CONST))

        self.grav_var.set(self.gravity)
        self.accel_var.set(self.accel)
        self.maxsp_var.set(self.max_speed)
        self.fric_en_var.set(self.friction_enabled)
        self.fric_frac_var.set(self.friction_frac)
        self.fric_const_var.set(self.friction_const)
        self.eff_w_var.set(self.effective_w)
        self.eff_h_var.set(self.effective_h)
        self.canvas.coords(self.boundary_id, 0, 0, self.effective_w, self.effective_h)

        for item in data.get("rectangles", []):
            self.rects.append(Rect.from_dict(self.canvas, item))
        self._update_selection_visual()

    def open_save_dialog(self):
        self._make_file_browser("Save Configuration As", "save")

    def open_load_dialog(self):
        self._make_file_browser("Load Configuration", "load")

    # ==================================================================
    # Tool option panels
    # ==================================================================
    def _clear_opt_body(self):
        for w in self.opt_body.winfo_children():
            w.pack_forget()

    def _build_arrow_options(self):
        self.arrow_frame = tk.Frame(self.opt_body, bg="#0f3460")
        tk.Label(
            self.arrow_frame,
            text="Drag any rectangle.\n\n"
                 "Velocity each tick =\n"
                 "direction of movement,\n"
                 "speed = min(|Δ|, max).\n\n"
                 "Free bodies are pushed\nas a stack. Supports\n"
                 "(grounded / resting)\nblock movement.",
            bg="#0f3460", fg="#ccc", font=("Segoe UI", 9), justify=tk.LEFT
        ).pack(anchor="w", padx=6, pady=8)

    def _build_add_options(self):
        self.add_frame = tk.Frame(self.opt_body, bg="#0f3460")
        self.random_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.add_frame, text="Random", variable=self.random_var,
            bg="#0f3460", fg="white", selectcolor="#1a1a2e",
            activebackground="#0f3460", font=("Segoe UI", 10),
            command=self._toggle_add_ui
        ).pack(anchor="w", padx=6, pady=4)

        tk.Label(self.add_frame, text="Width", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.add_w = tk.IntVar(value=70)
        self.add_sld_w = tk.Scale(
            self.add_frame, from_=20, to=180, orient=tk.HORIZONTAL,
            variable=self.add_w, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170
        )
        self.add_sld_w.pack(padx=4)

        tk.Label(self.add_frame, text="Height", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.add_h = tk.IntVar(value=50)
        self.add_sld_h = tk.Scale(
            self.add_frame, from_=20, to=160, orient=tk.HORIZONTAL,
            variable=self.add_h, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170
        )
        self.add_sld_h.pack(padx=4)

        tk.Label(self.add_frame, text="Color", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(6, 2))
        self.add_color = tk.StringVar(value=self.colors[0])
        cf = tk.Frame(self.add_frame, bg="#0f3460")
        cf.pack()
        self.add_color_btns = []
        for i, c in enumerate(self.colors):
            b = tk.Button(cf, bg=c, width=2, height=1, bd=2,
                          relief="sunken" if i == 0 else "raised",
                          command=lambda col=c: self._pick_add_color(col))
            b.grid(row=i // 5, column=i % 5, padx=2, pady=2)
            self.add_color_btns.append(b)

        self.add_grounded = tk.BooleanVar(value=False)
        self.add_chk_g = tk.Checkbutton(
            self.add_frame, text="Grounded (static)", variable=self.add_grounded,
            bg="#0f3460", fg="white", selectcolor="#1a1a2e",
            activebackground="#0f3460", font=("Segoe UI", 10)
        )
        self.add_chk_g.pack(anchor="w", padx=6, pady=8)
        tk.Label(self.add_frame, text="Left-click spawn\nRight-click delete",
                 bg="#0f3460", fg="#888", font=("Segoe UI", 8),
                 justify=tk.LEFT).pack(anchor="w", padx=6, pady=4)
        self._toggle_add_ui()

    def _toggle_add_ui(self):
        st = tk.DISABLED if self.random_var.get() else tk.NORMAL
        self.add_sld_w.config(state=st)
        self.add_sld_h.config(state=st)
        self.add_chk_g.config(state=st)
        for b in self.add_color_btns:
            b.config(state=st)

    def _pick_add_color(self, col):
        self.add_color.set(col)
        for b, c in zip(self.add_color_btns, self.colors):
            b.config(relief="sunken" if c == col else "raised")

    def _build_select_options(self):
        self.select_frame = tk.Frame(self.opt_body, bg="#0f3460")
        self.sel_info = tk.Label(
            self.select_frame, text="Click a rectangle\nto select it.",
            bg="#0f3460", fg="#ccc", font=("Segoe UI", 9), justify=tk.LEFT
        )
        self.sel_info.pack(anchor="w", padx=6, pady=6)

        tk.Label(self.select_frame, text="Width", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.sel_w = tk.IntVar(value=70)
        self.sel_sld_w = tk.Scale(
            self.select_frame, from_=20, to=180, orient=tk.HORIZONTAL,
            variable=self.sel_w, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170,
            command=self._apply_select_size
        )
        self.sel_sld_w.pack(padx=4)

        tk.Label(self.select_frame, text="Height", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.sel_h = tk.IntVar(value=50)
        self.sel_sld_h = tk.Scale(
            self.select_frame, from_=20, to=160, orient=tk.HORIZONTAL,
            variable=self.sel_h, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170,
            command=self._apply_select_size
        )
        self.sel_sld_h.pack(padx=4)

        tk.Label(self.select_frame, text="Color", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(6, 2))
        self.sel_color = tk.StringVar(value=self.colors[0])
        cf = tk.Frame(self.select_frame, bg="#0f3460")
        cf.pack()
        self.sel_color_btns = []
        for i, c in enumerate(self.colors):
            b = tk.Button(cf, bg=c, width=2, height=1, bd=2, relief="raised",
                          command=lambda col=c: self._pick_sel_color(col))
            b.grid(row=i // 5, column=i % 5, padx=2, pady=2)
            self.sel_color_btns.append(b)

        self.sel_grounded = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.select_frame, text="Grounded", variable=self.sel_grounded,
            bg="#0f3460", fg="white", selectcolor="#1a1a2e",
            activebackground="#0f3460", font=("Segoe UI", 10),
            command=self._apply_select_grounded
        ).pack(anchor="w", padx=6, pady=8)
        tk.Button(
            self.select_frame, text="Delete selected",
            bg="#e94560", fg="white", bd=0, pady=4,
            command=self._delete_selected
        ).pack(fill=tk.X, padx=8, pady=4)

    def _build_physics_options(self):
        """Physics tool – Notebook with Gravity + Friction tabs."""
        self.physics_frame = tk.Frame(self.opt_body, bg="#0f3460")

        nb = ttk.Notebook(self.physics_frame)
        nb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ---- Gravity tab ----
        tab_g = ttk.Frame(nb, padding=6)
        nb.add(tab_g, text="Gravity")

        ttk.Label(tab_g, text="Direction").pack(anchor="w", pady=(2, 4))
        self.grav_var = tk.StringVar(value=self.gravity)
        for val, lab in [("none", "None"), ("N", "North ↑"), ("E", "East →"),
                         ("S", "South ↓"), ("W", "West ←")]:
            ttk.Radiobutton(
                tab_g, text=lab, variable=self.grav_var, value=val,
                command=self._set_gravity
            ).pack(anchor="w", padx=8)

        ttk.Label(tab_g, text="Acceleration").pack(anchor="w", pady=(10, 0))
        self.accel_var = tk.DoubleVar(value=self.accel)
        tk.Scale(
            tab_g, from_=0.05, to=2.0, resolution=0.05,
            orient=tk.HORIZONTAL, variable=self.accel_var,
            bg="#f0f0f0", highlightthickness=0, length=170,
            command=self._set_accel
        ).pack(padx=4)

        ttk.Label(tab_g, text="Max speed").pack(anchor="w", pady=(8, 0))
        self.maxsp_var = tk.DoubleVar(value=self.max_speed)
        tk.Scale(
            tab_g, from_=2.0, to=40.0, resolution=0.5,
            orient=tk.HORIZONTAL, variable=self.maxsp_var,
            bg="#f0f0f0", highlightthickness=0, length=170,
            command=self._set_max_speed
        ).pack(padx=4)

        # ---- Friction tab ----
        tab_f = ttk.Frame(nb, padding=6)
        nb.add(tab_f, text="Friction")

        self.fric_en_var = tk.BooleanVar(value=self.friction_enabled)
        ttk.Checkbutton(
            tab_f, text="Enable friction", variable=self.fric_en_var,
            command=self._set_friction
        ).pack(anchor="w", pady=(2, 8))

        ttk.Label(tab_f, text="Loss fraction (⊥ gravity)").pack(anchor="w")
        self.fric_frac_var = tk.DoubleVar(value=self.friction_frac)
        tk.Scale(
            tab_f, from_=0.0, to=0.5, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.fric_frac_var,
            bg="#f0f0f0", highlightthickness=0, length=170,
            command=self._set_friction
        ).pack(padx=4)

        ttk.Label(tab_f, text="Static loss / distance").pack(anchor="w", pady=(8, 0))
        self.fric_const_var = tk.DoubleVar(value=self.friction_const)
        tk.Scale(
            tab_f, from_=0.0, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.fric_const_var,
            bg="#f0f0f0", highlightthickness=0, length=170,
            command=self._set_friction
        ).pack(padx=4)

        ttk.Label(
            tab_f,
            text="Applied each tick to the\n"
                 "velocity component\nperpendicular to gravity.\n"
                 "loss ≈ frac·|v⊥| + const·Δs",
            foreground="#666"
        ).pack(anchor="w", pady=10)

    def _build_canvas_options(self):
        self.canvas_frame = tk.Frame(self.opt_body, bg="#0f3460")
        tk.Label(self.canvas_frame, text="Effective size\n(playable area)",
                 bg="#0f3460", fg="#ccc", font=("Segoe UI", 9),
                 justify=tk.LEFT).pack(anchor="w", padx=6, pady=4)

        tk.Label(self.canvas_frame, text="Width", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.eff_w_var = tk.IntVar(value=self.effective_w)
        tk.Scale(
            self.canvas_frame, from_=200, to=self.canvas_w, orient=tk.HORIZONTAL,
            variable=self.eff_w_var, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170,
            command=self._apply_effective
        ).pack(padx=4)

        tk.Label(self.canvas_frame, text="Height", bg="#0f3460", fg="#aaa",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8)
        self.eff_h_var = tk.IntVar(value=self.effective_h)
        tk.Scale(
            self.canvas_frame, from_=150, to=self.canvas_h, orient=tk.HORIZONTAL,
            variable=self.eff_h_var, bg="#0f3460", fg="white",
            troughcolor="#1a1a2e", highlightthickness=0, length=170,
            command=self._apply_effective
        ).pack(padx=4)
        tk.Label(self.canvas_frame,
                 text="\nDrag on canvas to pan\n(view moves opposite\nto mouse).",
                 bg="#0f3460", fg="#888", font=("Segoe UI", 8),
                 justify=tk.LEFT).pack(anchor="w", padx=6, pady=8)

    # ==================================================================
    # Tool switching
    # ==================================================================
    def set_tool(self, key):
        self.current_tool = key
        self.selected_idx = None
        self.dragging = None
        self._update_selection_visual()
        for k, b in self.tool_btns.items():
            b.config(bg="#e94560" if k == key else "#1a1a2e")
        self._clear_opt_body()
        titles = {
            "arrow": "Arrow Tool", "add": "Add Rectangle",
            "select": "Select Tool", "physics": "Physics",
            "canvas": "Canvas Settings",
        }
        self.opt_title.config(text=titles.get(key, ""))
        {
            "arrow": self.arrow_frame, "add": self.add_frame,
            "select": self.select_frame, "physics": self.physics_frame,
            "canvas": self.canvas_frame,
        }[key].pack(fill=tk.BOTH, expand=True)
        if key == "select":
            self.sel_info.config(text="Click a rectangle\nto select it.")

    def _set_gravity(self):
        self.gravity = self.grav_var.get()
        for r in self.rects:
            r.resting = False

    def _set_accel(self, _=None):
        self.accel = float(self.accel_var.get())

    def _set_max_speed(self, _=None):
        self.max_speed = float(self.maxsp_var.get())

    def _set_friction(self, _=None):
        self.friction_enabled = bool(self.fric_en_var.get())
        self.friction_frac = float(self.fric_frac_var.get())
        self.friction_const = float(self.fric_const_var.get())

    def _apply_effective(self, _=None):
        self.effective_w = self.eff_w_var.get()
        self.effective_h = self.eff_h_var.get()
        self.canvas.coords(self.boundary_id, 0, 0, self.effective_w, self.effective_h)
        for r in self.rects:
            self.clamp_rect(r)
            r.redraw()

    # ==================================================================
    # Select helpers
    # ==================================================================
    def _load_select_ui(self, r):
        self.sel_w.set(int(r.w))
        self.sel_h.set(int(r.h))
        self.sel_grounded.set(r.grounded)
        self.sel_color.set(r.color)
        for b, c in zip(self.sel_color_btns, self.colors):
            b.config(relief="sunken" if c == r.color else "raised")
        self.sel_info.config(text=f"Selected  {int(r.w)}×{int(r.h)}")

    def _apply_select_size(self, _=None):
        if self.selected_idx is None:
            return
        r = self.rects[self.selected_idx]
        r.w = float(self.sel_w.get())
        r.h = float(self.sel_h.get())
        self.clamp_rect(r)
        r.redraw()
        self._update_selection_visual()

    def _pick_sel_color(self, col):
        self.sel_color.set(col)
        for b, c in zip(self.sel_color_btns, self.colors):
            b.config(relief="sunken" if c == col else "raised")
        if self.selected_idx is not None:
            r = self.rects[self.selected_idx]
            r.color = col
            self.canvas.itemconfig(r.id, fill=col)

    def _apply_select_grounded(self):
        if self.selected_idx is None:
            return
        r = self.rects[self.selected_idx]
        r.grounded = self.sel_grounded.get()
        if r.grounded:
            r.vx = r.vy = 0.0
            r.resting = False
        r.set_grounded_visual()

    def _delete_selected(self):
        if self.selected_idx is None:
            return
        r = self.rects.pop(self.selected_idx)
        self.canvas.delete(r.id)
        self.selected_idx = None
        self._update_selection_visual()
        self.sel_info.config(text="Click a rectangle\nto select it.")

    def _update_selection_visual(self):
        for i, r in enumerate(self.rects):
            if i == self.selected_idx:
                self.canvas.itemconfig(r.id, outline="#00ffcc", width=3)
            else:
                r.set_grounded_visual()

    # ==================================================================
    # Menu / pause
    # ==================================================================
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

    def reset(self):
        for r in self.rects:
            self.canvas.delete(r.id)
        self.rects.clear()
        self.selected_idx = None
        self.dragging = None
        self.continue_game()

    # ==================================================================
    # Creation
    # ==================================================================
    def create_rect(self, cx, cy):
        if self.random_var.get():
            w = random.randint(40, 100)
            h = random.randint(30, 80)
            color = random.choice(self.colors)
            grounded = False
        else:
            w = self.add_w.get()
            h = self.add_h.get()
            color = self.add_color.get()
            grounded = self.add_grounded.get()

        x = max(0, min(cx - w / 2, self.effective_w - w))
        y = max(0, min(cy - h / 2, self.effective_h - h))
        rect = Rect(self.canvas, x, y, w, h, color, grounded)
        self.rects.append(rect)
        self._resolve_spawn(rect)
        return rect

    def _resolve_spawn(self, new_r):
        for other in self.rects:
            if other is new_r:
                continue
            ox, oy = self._overlap(new_r, other)
            if ox <= 0 or oy <= 0:
                continue
            self._positional_separate(new_r, other)
            new_r.redraw()
            other.redraw()

    def find_rect_at(self, x, y):
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        for i in range(len(self.rects) - 1, -1, -1):
            r = self.rects[i]
            if r.x <= cx <= r.x + r.w and r.y <= cy <= r.y + r.h:
                return i
        return None

    # ==================================================================
    # Input
    # ==================================================================
    def on_left_press(self, event):
        if self.menu_visible:
            return
        x, y = event.x, event.y
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)

        if self.current_tool == "add":
            self.create_rect(cx, cy)
        elif self.current_tool == "arrow":
            idx = self.find_rect_at(x, y)
            if idx is not None:
                r = self.rects[idx]
                self.dragging = (idx, cx - r.x, cy - r.y)
                self.canvas.tag_raise(r.id)
                r.vx = r.vy = 0.0
                r.resting = False
        elif self.current_tool == "select":
            idx = self.find_rect_at(x, y)
            self.selected_idx = idx
            self._update_selection_visual()
            if idx is not None:
                self._load_select_ui(self.rects[idx])
            else:
                self.sel_info.config(text="Click a rectangle\nto select it.")
        elif self.current_tool == "canvas":
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
            idx = self.dragging[0]
            r = self.rects[idx]
            r.clamp_speed(self.max_speed)
            if r.grounded:
                r.vx = r.vy = 0.0
        self.dragging = None

    def on_right_click(self, event):
        if self.menu_visible or self.current_tool != "add":
            return
        idx = self.find_rect_at(event.x, event.y)
        if idx is not None:
            r = self.rects.pop(idx)
            self.canvas.delete(r.id)
            if self.selected_idx == idx:
                self.selected_idx = None
            elif self.selected_idx is not None and self.selected_idx > idx:
                self.selected_idx -= 1

    # ==================================================================
    # Main loop
    # ==================================================================
    def update_loop(self):
        if not self.paused:
            self.apply_gravity_accel()
            self.integrate()
            self.resolve_collisions()
        self.root.after(self.timer_interval, self.update_loop)

    def _sync_effective(self):
        self.eff_w_var.set(self.effective_w)
        self.eff_h_var.set(self.effective_h)
        self.canvas.coords(self.boundary_id, 0, 0, self.effective_w, self.effective_h)

if __name__ == "__main__":
    root = tk.Tk()
    app = RectangleApp(root)
    root.mainloop()
