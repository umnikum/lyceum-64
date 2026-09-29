import tkinter as tk
import math
import os
import re

# ------------------------------------------------------------
# Global settings
# ------------------------------------------------------------
BELT_SPEED = 2.8
MARKER_SPACING = 36
MARKER_SIZE = 12
ROTARY_FRICTION = 0.78
LINEAR_DAMPING = 0.88
COLLISION_ITERATIONS = 5


class Conveyor:
    def __init__(self, canvas, x, y, length, thickness, direction=1,
                 orientation="horizontal", fill="#3a3a4a", marker_fill="#666"):
        self.canvas = canvas
        self.x, self.y = x, y
        self.length, self.thickness = length, thickness
        self.direction = direction          # +1 or -1 along the travel axis
        self.orientation = orientation      # "horizontal" | "vertical"
        self.running = True
        self.phase = 0.0

        if orientation == "horizontal":
            self.x2, self.y2 = x + length, y + thickness
        else:  # vertical
            self.x2, self.y2 = x + thickness, y + length

        self.bg_id = canvas.create_rectangle(self.x, self.y, self.x2, self.y2,
                                             fill=fill, outline="#222", width=2)
        self.markers = [canvas.create_rectangle(0, 0, 1, 1, fill=marker_fill, outline="")
                        for _ in range(int(length / MARKER_SPACING) + 3)]
        self.arrows = [canvas.create_polygon(0, 0, 0, 0, 0, 0, fill="#00e676") for _ in range(3)]
        self._update_markers()
        self._update_arrows()

    def _update_arrows(self):
        s = 8
        if self.orientation == "horizontal":
            spacing = self.length / 4
            by = self.y2 + 16
            for i, arr in enumerate(self.arrows):
                cx = self.x + spacing * (i + 1)
                if self.direction > 0:
                    pts = [cx - s, by - s, cx - s, by + s, cx + s, by]
                else:
                    pts = [cx + s, by - s, cx + s, by + s, cx - s, by]
                self.canvas.coords(arr, *pts)
        else:
            spacing = self.length / 4
            bx = self.x2 + 16
            for i, arr in enumerate(self.arrows):
                cy = self.y + spacing * (i + 1)
                if self.direction > 0:
                    pts = [bx - s, cy - s, bx + s, cy - s, bx, cy + s]
                else:
                    pts = [bx - s, cy + s, bx + s, cy + s, bx, cy - s]
                self.canvas.coords(arr, *pts)

    def _update_markers(self):
        for i, mid in enumerate(self.markers):
            off = (self.phase + i * MARKER_SPACING) % self.length
            if self.orientation == "horizontal":
                mx = self.x + off
                my = self.y + self.thickness / 2
                self.canvas.coords(mid, mx - MARKER_SIZE / 2, my - MARKER_SIZE / 4,
                                   mx + MARKER_SIZE / 2, my + MARKER_SIZE / 4)
            else:
                mx = self.x + self.thickness / 2
                my = self.y + off
                self.canvas.coords(mid, mx - MARKER_SIZE / 4, my - MARKER_SIZE / 2,
                                   mx + MARKER_SIZE / 4, my + MARKER_SIZE / 2)

    def update_markers(self):
        if self.running:
            self.phase = (self.phase + BELT_SPEED * self.direction) % self.length
        self._update_markers()

    def contains_point(self, px, py):
        return self.x <= px <= self.x2 and self.y <= py <= self.y2

    def get_velocity(self):
        if not self.running:
            return 0.0, 0.0
        v = BELT_SPEED * self.direction
        return (v, 0.0) if self.orientation == "horizontal" else (0.0, v)

    def reverse(self):
        self.direction *= -1
        self._update_arrows()

    def set_running(self, state):
        self.running = state


class MovingRectangle:
    def __init__(self, canvas, cx, cy, w, h, angle=0.0, **kwargs):
        self.canvas = canvas
        self.cx, self.cy = cx, cy
        self.w, self.h = w, h
        self.angle = angle
        self.vx = self.vy = self.omega = 0.0
        self.id = None
        self.kwargs = kwargs
        self.on_belt = False
        self.alive = True
        self.update()

    def _get_corners(self):
        hw, hh = self.w / 2, self.h / 2
        rad = math.radians(self.angle)
        c, s = math.cos(rad), math.sin(rad)
        local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return [(x * c - y * s + self.cx, x * s + y * c + self.cy) for x, y in local]

    def update(self):
        if not self.alive:
            return
        pts = [c for xy in self._get_corners() for c in xy]
        if self.id is None:
            self.id = self.canvas.create_polygon(pts, **self.kwargs)
        else:
            self.canvas.coords(self.id, *pts)

    def move(self, dt=1.0):
        if not self.alive:
            return
        self.cx += self.vx * dt
        self.cy += self.vy * dt
        self.angle = (self.angle + self.omega * dt) % 360
        self.update()

    def destroy(self):
        if self.id and self.alive:
            self.canvas.delete(self.id)
            self.alive = False


class DistanceSensor:
    def __init__(self, canvas, x, y, direction_deg=90, max_range=150,
                 color="#00b4d8", sid=1, attached_to=None, local_offset=(0, 0),
                 local_dir_offset=0.0):
        """
        If attached_to is a MovingRectangle (the handle), the sensor follows
        the handle position + orientation each frame.
        local_offset is in the handle's local frame (x along handle length,
        y perpendicular). local_dir_offset is added to the handle angle.
        """
        self.canvas = canvas
        self.x, self.y = x, y
        self.direction_deg = direction_deg
        self.max_range = max_range
        self.sid = sid
        self.distance = None
        self.attached_to = attached_to
        self.local_offset = local_offset
        self.local_dir_offset = local_dir_offset

        rad = math.radians(direction_deg)
        self.dx, self.dy = math.cos(rad), math.sin(rad)

        size = 12
        bx, by = x - self.dx * size, y - self.dy * size
        px, py = -self.dy * (size * 0.55), self.dx * (size * 0.55)
        self.tri_id = canvas.create_polygon(x, y, bx + px, by + py, bx - px, by - py,
                                            fill=color, outline="white")
        self.ray_id = canvas.create_line(x, y, x + self.dx * max_range, y + self.dy * max_range,
                                         fill=color, width=2, dash=(5, 3))
        lx = x - self.dx * 20
        ly = y - self.dy * 20
        self.label_id = canvas.create_text(lx, ly, text="--", fill="white",
                                           font=("Consolas", 10, "bold"))

    def _sync_pose(self):
        """Update world position & direction if attached to the handle."""
        if self.attached_to is None or not self.attached_to.alive:
            return
        h = self.attached_to
        rad = math.radians(h.angle)
        c, s = math.cos(rad), math.sin(rad)
        ox, oy = self.local_offset
        # local → world
        self.x = h.cx + ox * c - oy * s
        self.y = h.cy + ox * s + oy * c
        world_dir = (h.angle + self.local_dir_offset) % 360
        self.direction_deg = world_dir
        rad = math.radians(world_dir)
        self.dx, self.dy = math.cos(rad), math.sin(rad)

        # redraw triangle
        size = 12
        bx = self.x - self.dx * size
        by = self.y - self.dy * size
        px, py = -self.dy * (size * 0.55), self.dx * (size * 0.55)
        self.canvas.coords(self.tri_id,
                           self.x, self.y,
                           bx + px, by + py,
                           bx - px, by - py)

    def _intersect(self, x1, y1, x2, y2):
        rx, ry = self.dx, self.dy
        sx, sy = x2 - x1, y2 - y1
        den = rx * sy - ry * sx
        if abs(den) < 1e-8:
            return None
        t = ((x1 - self.x) * sy - (y1 - self.y) * sx) / den
        u = ((x1 - self.x) * ry - (y1 - self.y) * rx) / den
        if t >= 0 and 0 <= u <= 1:
            return t
        return None

    def update(self, dynamics):
        self._sync_pose()

        min_t = self.max_range
        hit = False
        for obj in dynamics:
            if not obj.alive:
                continue
            # ignore the handle itself when the sensor is attached to it
            if self.attached_to is not None and obj is self.attached_to:
                continue
            corners = obj._get_corners()
            for i in range(4):
                t = self._intersect(*corners[i], *corners[(i + 1) % 4])
                if t is not None and t < min_t:
                    min_t = t
                    hit = True
        if hit:
            self.distance = min_t
            self.canvas.coords(self.ray_id, self.x, self.y,
                               self.x + self.dx * min_t, self.y + self.dy * min_t)
            self.canvas.itemconfig(self.label_id, text=f"{min_t:.0f}")
        else:
            self.distance = None
            self.canvas.coords(self.ray_id, self.x, self.y,
                               self.x + self.dx * self.max_range,
                               self.y + self.dy * self.max_range)
            self.canvas.itemconfig(self.label_id, text="--")

        # keep label near the sensor
        lx = self.x - self.dx * 20
        ly = self.y - self.dy * 20
        self.canvas.coords(self.label_id, lx, ly)


class Spawner:
    def __init__(self, canvas, belt, side="left", width=70, color="#2a9d8f", name="Spawner"):
        """
        side for horizontal belt: "left" | "right"
        side for vertical belt:   "top"  | "bottom"
        """
        self.canvas = canvas
        self.belt = belt
        self.side = side
        self.name = name
        self.cargo = []
        self.interval = 70
        self.timer = 0
        self.auto = True
        self.enabled = True

        if belt.orientation == "horizontal":
            self.w, self.h = width, belt.thickness
            if side == "left":
                self.x = belt.x - width
                self.entry_x = belt.x + 20
            else:  # right
                self.x = belt.x2
                self.entry_x = belt.x2 - 20
            self.y = belt.y
            self.entry_y = belt.y + belt.thickness / 2
        else:  # vertical belt
            self.w, self.h = belt.thickness, width
            self.x = belt.x
            self.entry_x = belt.x + belt.thickness / 2
            if side == "top":
                self.y = belt.y - width
                self.entry_y = belt.y + 20
            else:  # bottom
                self.y = belt.y2
                self.entry_y = belt.y2 - 20

        self.rect_id = canvas.create_rectangle(self.x, self.y, self.x + self.w, self.y + self.h,
                                               fill=color, outline="white", width=2)
        self.label_id = canvas.create_text(self.x + self.w / 2, self.y + self.h / 2, text=name,
                                           fill="white", font=("Arial", 8, "bold"))
        canvas.tag_bind(self.rect_id, "<Button-1>", self.open_settings)
        canvas.tag_bind(self.label_id, "<Button-1>", self.open_settings)

    def spawn_one(self, engine):
        if not self.enabled or not self.cargo:
            return None
        item = self.cargo.pop(0)
        # rel_across is offset perpendicular to travel
        if self.belt.orientation == "horizontal":
            cx = self.entry_x
            cy = self.entry_y + item["rel_across"]
        else:
            cx = self.entry_x + item["rel_across"]
            cy = self.entry_y
        rect = MovingRectangle(self.canvas, cx, cy,
                               item["w"], item["h"], angle=item["angle"],
                               fill=item["fill"], outline="white", width=2)
        engine.register(rect, "dynamic")
        return rect

    def add_cargo(self, w=65, h=36, rel_across=0.0, angle=0.0, fill="#4cc9f0"):
        self.cargo.append(dict(w=w, h=h, rel_across=rel_across, angle=angle, fill=fill))

    def update(self, engine):
        if self.auto and self.enabled and self.belt.running and self.interval > 0:
            self.timer += 1
            if self.timer >= self.interval:
                self.timer = 0
                if self.cargo:
                    self.spawn_one(engine)
                else:
                    for i in range(4):
                        self.add_cargo(w=60, h=34, rel_across=(i % 3 - 1) * 6,
                                       fill=["#4cc9f0", "#90be6d", "#f9c74f", "#f8961e"][i % 4])

    def open_settings(self, event=None):
        top = tk.Toplevel(self.canvas.master)
        top.title(self.name)
        top.geometry("240x160")
        iv = tk.IntVar(value=self.interval)
        av = tk.BooleanVar(value=self.auto)
        ev = tk.BooleanVar(value=self.enabled)
        tk.Label(top, text="Interval (0=manual)").pack()
        tk.Spinbox(top, from_=0, to=600, textvariable=iv, width=6).pack()
        tk.Checkbutton(top, text="Auto", variable=av).pack()
        tk.Checkbutton(top, text="Enabled", variable=ev).pack()
        tk.Label(top, text=f"Cargo: {len(self.cargo)}").pack(pady=4)

        def apply():
            self.interval, self.auto, self.enabled = iv.get(), av.get(), ev.get()
            top.destroy()

        tk.Button(top, text="Apply", command=apply).pack()


class Collector:
    def __init__(self, canvas, x, y, w, h,
                 sensor_x=None, sensor_y=None, sensor_y1=None, sensor_y2=None,
                 sensor_x1=None, sensor_x2=None,
                 orientation="horizontal", color="#e76f51", name="Collector",
                 linked_spawner=None):
        """
        orientation="horizontal" → packages travel along X; sensor is a vertical line
        orientation="vertical"   → packages travel along Y; sensor is a horizontal line
        """
        self.canvas = canvas
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.orientation = orientation
        self.cargo = []
        self.name = name
        self.linked_spawner = linked_spawner

        if orientation == "horizontal":
            # vertical sensor line
            self.sensor_x = sensor_x if sensor_x is not None else x + w / 2
            self.sensor_y1 = sensor_y1 if sensor_y1 is not None else y - 4
            self.sensor_y2 = sensor_y2 if sensor_y2 is not None else y + h + 4
            self.line_id = canvas.create_line(
                self.sensor_x, self.sensor_y1, self.sensor_x, self.sensor_y2,
                fill="#ffcc00", width=3, dash=(4, 2))
        else:
            # horizontal sensor line
            self.sensor_y = sensor_y if sensor_y is not None else y + h / 2
            self.sensor_x1 = sensor_x1 if sensor_x1 is not None else x - 4
            self.sensor_x2 = sensor_x2 if sensor_x2 is not None else x + w + 4
            self.line_id = canvas.create_line(
                self.sensor_x1, self.sensor_y, self.sensor_x2, self.sensor_y,
                fill="#ffcc00", width=3, dash=(4, 2))

        self.rect_id = canvas.create_rectangle(self.x, self.y, self.x + self.w, self.y + self.h,
                                               fill=color, outline="white", width=2)
        self.label_id = canvas.create_text(self.x + self.w / 2, self.y + self.h / 2, text=name,
                                           fill="white", font=("Arial", 8, "bold"))
        canvas.tag_bind(self.rect_id, "<Button-1>", self.open_inventory)
        canvas.tag_bind(self.label_id, "<Button-1>", self.open_inventory)
    
    def open_inventory(self, event=None):
        top = tk.Toplevel(self.canvas.master)
        top.title(self.name)
        top.geometry("220x140")
        top.resizable(False, False)

        n = len(self.cargo)
        linked = self.linked_spawner is not None
        link_txt = f"Yes → {self.linked_spawner.name}" if linked else "No"

        tk.Label(top, text=f"Inventory: {n} item(s)",
                 font=("Arial", 11, "bold")).pack(pady=(12, 4))
        tk.Label(top, text=f"Linked to spawner: {link_txt}").pack(pady=2)

        if linked and n > 0:
            def transfer():
                # move all cargo into the linked spawner queue
                self.linked_spawner.cargo.extend(self.cargo)
                self.cargo.clear()
                top.destroy()
            tk.Button(top, text="Transfer to Spawner", command=transfer).pack(pady=8)
        else:
            tk.Button(top, text="Close", command=top.destroy).pack(pady=8)

    @classmethod
    def from_belt(cls, canvas, belt, side="right", width=70, color="#e76f51",
                  name="Collector", linked_spawner=None):
        if belt.orientation == "horizontal":
            h = belt.thickness
            if side == "left":
                x = belt.x - width
                sensor_x = belt.x + 6
            else:
                x = belt.x2
                sensor_x = belt.x2 - 6
            return cls(canvas, x, belt.y, width, h,
                       sensor_x=sensor_x, sensor_y1=belt.y - 4, sensor_y2=belt.y2 + 4,
                       orientation="horizontal", color=color, name=name,
                       linked_spawner=linked_spawner)
        else:  # vertical belt
            w = belt.thickness
            if side == "top":
                y = belt.y - width
                sensor_y = belt.y + 6
            else:
                y = belt.y2
                sensor_y = belt.y2 - 6
            return cls(canvas, belt.x, y, w, width,
                       sensor_y=sensor_y, sensor_x1=belt.x - 4, sensor_x2=belt.x2 + 4,
                       orientation="vertical", color=color, name=name,
                       linked_spawner=linked_spawner)

    def try_collect(self, rect, engine):
        if not rect.alive:
            return False
        if self.orientation == "horizontal":
            hit = (self.sensor_y1 <= rect.cy <= self.sensor_y2 and
                   abs(rect.cx - self.sensor_x) < 18)
            rel = rect.cy - (self.y + self.h / 2)
        else:
            hit = (self.sensor_x1 <= rect.cx <= self.sensor_x2 and
                   abs(rect.cy - self.sensor_y) < 18)
            rel = rect.cx - (self.x + self.w / 2)
        if hit:
            self.cargo.append(dict(w=rect.w, h=rect.h, rel_across=rel,
                                   angle=rect.angle, fill=rect.kwargs.get("fill", "#4cc9f0")))
            engine.unregister(rect)
            rect.destroy()
            return True
        return False



class CollisionEngine:
    def __init__(self):
        self.dynamics = []
        self.ethereals = []

    def register(self, obj, typ):
        if typ == "dynamic":
            self.dynamics.append(obj)
        elif typ == "ethereal":
            self.ethereals.append(obj)

    def unregister(self, obj):
        if obj in self.dynamics:
            self.dynamics.remove(obj)

    def _rect_rect(self, a, b):
        dx, dy = b.cx - a.cx, b.cy - a.cy
        dist = math.hypot(dx, dy) or 1e-6
        ra = 0.32 * math.hypot(a.w, a.h)
        rb = 0.32 * math.hypot(b.w, b.h)
        ov = ra + rb - dist
        if ov <= 0:
            return
        nx, ny = dx / dist, dy / dist
        push = ov * 0.5
        a.cx -= nx * push
        a.cy -= ny * push
        b.cx += nx * push
        b.cy += ny * push
        va = a.vx * nx + a.vy * ny
        vb = b.vx * nx + b.vy * ny
        a.vx += (vb - va) * nx * 0.35
        a.vy += (vb - va) * ny * 0.35
        b.vx += (va - vb) * nx * 0.35
        b.vy += (va - vb) * ny * 0.35

    def resolve(self):
        for r in self.dynamics:
            if not r.alive:
                continue
            r.on_belt = False
            for e in self.ethereals:
                if isinstance(e, Conveyor) and any(e.contains_point(x, y) for x, y in r._get_corners()):
                    r.on_belt = True
                    r.vx, r.vy = e.get_velocity()
                    r.omega *= ROTARY_FRICTION
                    break
            if not r.on_belt:
                r.vx *= LINEAR_DAMPING
                r.vy *= LINEAR_DAMPING
                r.omega *= 0.93

        for _ in range(COLLISION_ITERATIONS):
            n = len(self.dynamics)
            for i in range(n):
                if not self.dynamics[i].alive:
                    continue
                for j in range(i + 1, n):
                    if self.dynamics[j].alive:
                        self._rect_rect(self.dynamics[i], self.dynamics[j])


# ------------------------------------------------------------
# 4-limb / 5-rotor Robotic Arm
# ------------------------------------------------------------
class RoboticArm:
    """
    R1 (base) - L1 - R2 - L2 - R3 - L3 - R4 - L4 - R5 (handle) - Handle
    All commands are relative:  R3 25   = add +25° to current R3
                               R3 25 CC = add -25°
    """
    def __init__(self, canvas, base_x, base_y, engine,
                 lengths=(80, 80, 40, 20), max_speed=2.6):
        self.canvas = canvas
        self.base_x, self.base_y = base_x, base_y
        self.engine = engine
        self.lengths = list(lengths)          # 4 limbs
        self.max_speed = max_speed
        self.n_joints = 5                     # R1 … R5

        # Bend limits for intermediate joints (R2,R3,R4) – 0° = straight
        self.joint_min = [None, 5.0, 5.0, 185.0, None]   # index 0 unused
        self.joint_max = [None, 175.0, 175.0, 355.0, None]

        # Default folded pose
        self.angles = [-120.0, 120.0, 120.0, 330.0, 0.0]   # R1…R5
        self.targets = list(self.angles)
        self.dirs = [1] * self.n_joints

        # ----- visuals -----
        colors = ["#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#f72585"]
        self.rotors = []
        for i, col in enumerate(colors):
            oid = canvas.create_oval(0, 0, 1, 1, fill=col, outline="white", width=2)
            self.rotors.append(oid)

        self.limbs = []
        for _ in range(4):
            lid = canvas.create_line(0, 0, 0, 0, fill="#adb5bd", width=7, capstyle=tk.ROUND)
            self.limbs.append(lid)

        # solid handle
        self.handle = MovingRectangle(canvas, base_x, base_y, 18, 18,
                                      fill="#f72585", outline="white", width=2)
        engine.register(self.handle, "dynamic")

        self.detectors = {}
        self.commands = []
        self.cmd_idx = 0
        self.waiting_condition = None

        self.load_commands("RoboticArm.txt")
        self._update_kinematics()

    def add_detector(self, sensor):
        self.detectors[sensor.sid] = sensor

    def _update_kinematics(self):
        x, y = self.base_x, self.base_y
        accum = 0.0
        points = [(x, y)]

        for i in range(4):                      # 4 limbs
            accum += self.angles[i]
            rad = math.radians(accum)
            x += self.lengths[i] * math.cos(rad)
            y += self.lengths[i] * math.sin(rad)
            points.append((x, y))

        # draw rotors
        r = 10
        for i, (px, py) in enumerate(points):
            self.canvas.coords(self.rotors[i], px - r, py - r, px + r, py + r)

        # draw limbs
        for i in range(4):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.canvas.coords(self.limbs[i], x1, y1, x2, y2)

        # handle at last point, orientation = total of all 5 joints
        accum += self.angles[4]                 # add R5
        self.handle.cx, self.handle.cy = points[-1]
        self.handle.angle = accum
        self.handle.update()

    def _step_angle(self, current, target, direction_pref, max_spd):
        diff = (target - current) % 360
        if diff > 180:
            diff -= 360
        if direction_pref < 0:
            if diff >= 0:
                diff -= 360
            else:
                diff += 360
        if abs(diff) <= max_spd:
            return target % 360, True
        return (current + math.copysign(max_spd, diff)) % 360, False

    def update(self):
        for i in range(self.n_joints):
            self.angles[i], _ = self._step_angle(
                self.angles[i], self.targets[i], self.dirs[i], self.max_speed)

            # apply limits to intermediate joints
            if self.joint_min[i] is not None:
                self.angles[i] = max(self.joint_min[i],
                                     min(self.joint_max[i], self.angles[i]))

        self._update_kinematics()
        self._process_commands()

    # ---------- command system (relative, R1…R5) ----------
    def load_commands(self, filename):
        if not os.path.exists(filename):
            self._create_sample_file(filename)

        raw = []
        with open(filename, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.split("#", 1)[0].strip()
                if ln:
                    raw.append(ln)
        self.commands = raw
        self.cmd_idx = 0
        self.waiting_condition = None
        print(f"Loaded {len(self.commands)} commands from {filename}")

    def _create_sample_file(self, filename):
        sample = """# 4-limb / 5-rotor arm
# Relative commands: R2 30 = add +30° to current R2
# D0 is now a distance sensor on the hand pointing "down" (bottom of handle)

WAIT D1 < 80 OR D2 < 80
WAIT D1 > 130 OR D2 > 130

STOP

# Unfold toward the belt
R1 20
R2 20
R3 -40
R4 -30
R5 0

# Wait until something is close under the hand (D0 distance)
WAIT D0 < 40

# Fold back toward home
R1 -20
R2 -20
R3 40
R4 30
R5 0

RESUME

WAIT D3 < 80 OR D4 < 80
WAIT D3 > 130 OR D4 > 130
"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(sample)
        print(f"Created sample {filename}")

    def _eval_condition(self, expr):
        expr = expr.upper()
        expr = expr.replace("AND", " and ").replace("OR", " or ").replace("NOT", " not ")

        def repl(m):
            sid = int(m.group(1))
            sens = self.detectors.get(sid)
            val = sens.distance if (sens and sens.distance is not None) else 9999.0
            return str(val)

        expr = re.sub(r"D(\d+)", repl, expr)
        try:
            return bool(eval(expr, {"__builtins__": {}}))
        except Exception:
            return False

    def _process_commands(self):
        if not self.commands:
            return

        if self.waiting_condition is not None:
            if self._eval_condition(self.waiting_condition):
                self.waiting_condition = None
                self.cmd_idx += 1
            return

        if self.cmd_idx >= len(self.commands):
            self.cmd_idx = 0

        line = self.commands[self.cmd_idx]
        parts = line.split()
        if not parts:
            self.cmd_idx += 1
            return

        cmd = parts[0].upper()

        if cmd in ("R1", "R2", "R3", "R4", "R5"):
            try:
                delta = float(parts[1])
            except (IndexError, ValueError):
                self.cmd_idx += 1
                return

            force_cc = any(t.upper() == "CC" for t in parts[2:])
            if force_cc:
                delta = -delta

            idx = int(cmd[1]) - 1          # R1 → 0, R5 → 4
            new_target = self.angles[idx] + delta

            # clamp intermediate joints
            if self.joint_min[idx] is not None:
                new_target = max(self.joint_min[idx],
                                 min(self.joint_max[idx], new_target))

            self.targets[idx] = new_target
            self.dirs[idx] = 1
            self.cmd_idx += 1

        elif cmd == "STOP":
            for e in self.engine.ethereals:
                if isinstance(e, Conveyor):
                    e.set_running(False)
            self.cmd_idx += 1

        elif cmd == "RESUME":
            for e in self.engine.ethereals:
                if isinstance(e, Conveyor):
                    e.set_running(True)
            self.cmd_idx += 1

        elif cmd == "WAIT":
            self.waiting_condition = " ".join(parts[1:])

        else:
            self.cmd_idx += 1


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
class ConveyorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Conveyor + 4-Limb / 5-Rotor Arm")
        self.root.geometry("1100x720")

        self.canvas = tk.Canvas(root, width=1080, height=600, bg="#0f0f1a")
        self.canvas.pack(pady=5)

        bf = tk.Frame(root)
        bf.pack()
        self.paused = False
        self.pause_btn = tk.Button(bf, text="Pause", width=12, command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(bf, text="Reverse Belt", width=11, command=self.reverse_belt).pack(side=tk.LEFT, padx=5)
        tk.Button(bf, text="Spawn", width=8, command=self.force_spawn).pack(side=tk.LEFT, padx=5)

        belt_y, thick = 380, 60
        self.belt = Conveyor(self.canvas, 180, belt_y, 720, thick, direction=1)

        self.spawner = Spawner(self.canvas, self.belt, side="left", width=70, name="Spawner")
        for i in range(6):
            self.spawner.add_cargo(w=60, h=34, rel_across=(i % 3 - 1) * 6,
                                   fill=["#4cc9f0", "#90be6d", "#f9c74f", "#f8961e"][i % 4])

        # original right-side collector on the belt
        self.collector = Collector.from_belt(
            self.canvas, self.belt, side="right", width=70, name="Collector")

        # EXTRA collector below the arm (under the working area)
        arm_x = 180 + 300
        arm_y = belt_y - 20
        self.arm_collector = Collector(
            self.canvas,
            x=arm_x - 20,
            y=belt_y + thick + 10,
            w=40, h=100,                    # tall / narrow
            sensor_y=belt_y + thick + 30,   # horizontal trip line
            sensor_x1=arm_x - 24,
            sensor_x2=arm_x + 24,
            orientation="vertical",
            color="#e9c46a",
            name="ArmDrop"
        )

        self.engine = CollisionEngine()
        self.engine.register(self.belt, "ethereal")

        self.arm = RoboticArm(self.canvas, arm_x, arm_y, self.engine, lengths=(80, 100, 40, 40))

        # Sensors D1–D4 (fixed, as before)
        s1 = DistanceSensor(self.canvas, arm_x - 10, belt_y - 25, 90, 130, "#00b4d8", sid=1)
        s2 = DistanceSensor(self.canvas, arm_x - 10, belt_y + thick + 25, 270, 130, "#90e0ef", sid=2)
        s3 = DistanceSensor(self.canvas, arm_x + 140, belt_y - 25, 90, 130, "#00b4d8", sid=3)
        s4 = DistanceSensor(self.canvas, arm_x + 140, belt_y + thick + 25, 270, 130, "#90e0ef", sid=4)

        # D0 – distance sensor attached to the hand, pointing toward the
        # "bottom" of the handle (local +90° relative to handle orientation)
        s0 = DistanceSensor(
            self.canvas,
            x=arm_x, y=arm_y,          # initial; will be overwritten by attachment
            direction_deg=90,
            max_range=120,
            color="#ff9f1c",
            sid=0,
            attached_to=self.arm.handle,
            local_offset=(0, 10),      # slightly offset from handle centre
            local_dir_offset=0.0      # +90° → points "down" relative to handle
        )

        for s in (s0, s1, s2, s3, s4):
            self.arm.add_detector(s)
            self.engine.register(s, "ethereal")
        self.sensors = [s0, s1, s2, s3, s4]

        self.collectors = [self.collector, self.arm_collector]

        self.animate()

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.config(text="Continue" if self.paused else "Pause")

    def reverse_belt(self):
        self.belt.reverse()

    def force_spawn(self):
        self.spawner.spawn_one(self.engine)

    def animate(self):
        if not self.paused:
            self.belt.update_markers()
            self.spawner.update(self.engine)

            for r in list(self.engine.dynamics):
                for col in self.collectors:
                    if col.try_collect(r, self.engine):
                        break

            self.engine.resolve()
            for r in self.engine.dynamics:
                if r is not self.arm.handle:
                    r.move()

            for s in self.sensors:
                s.update(self.engine.dynamics)
            self.arm.update()

        self.root.after(16, self.animate)


if __name__ == "__main__":
    root = tk.Tk()
    app = ConveyorApp(root)
    root.mainloop()
