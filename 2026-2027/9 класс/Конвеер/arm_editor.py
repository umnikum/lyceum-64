import tkinter as tk
from tkinter import scrolledtext
import math

class RoboticArm:
    """
    4-limb / 5-rotor arm.
    R1 (base) – L1 – R2 – L2 – R3 – L3 – R4 – L4 – R5 (handle)
    Joint limits (hard):
        R2, R3 : 5° … 175°
        R4     : 185° … 355°
        R1, R5 : unlimited
    """
    def __init__(self, canvas, base_x, base_y, lengths=(80, 80, 40, 20)):
        self.canvas = canvas
        self.base_x, self.base_y = base_x, base_y
        self.lengths = list(lengths)
        self.n_joints = 5

        self.joint_min = [None, 5.0, 5.0, 185.0, None]
        self.joint_max = [None, 175.0, 175.0, 355.0, None]
        self.default_angles = [-120.0, 120.0, 120.0, 330.0, 0.0]
        self.angles = list(self.default_angles)

        colors = ["#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#f72585"]
        self.rotors = []
        self.angle_labels = []
        for i, col in enumerate(colors):
            oid = canvas.create_oval(0, 0, 1, 1, fill=col, outline="black", width=2,
                                     tags=("rotor", f"rotor{i}"))
            self.rotors.append(oid)
            lid = canvas.create_text(0, 0, text="", fill="black",
                                     font=("Arial", 9, "bold"),
                                     tags=("label", f"label{i}"))
            self.angle_labels.append(lid)

        self.limbs = []
        for i in range(4):
            lid = canvas.create_line(0, 0, 0, 0, fill="#555555", width=8,
                                     capstyle=tk.ROUND, tags=("limb", f"limb{i}"))
            self.limbs.append(lid)

        self.handle_line = canvas.create_line(0, 0, 0, 0, fill="#f72585", width=6,
                                               capstyle=tk.ROUND, tags="handle")
        self._update_kinematics()

    def _update_kinematics(self):
        x, y = self.base_x, self.base_y
        accum = 0.0
        points = [(x, y)]

        for i in range(4):
            accum += self.angles[i]
            rad = math.radians(accum)
            x += self.lengths[i] * math.cos(rad)
            y += self.lengths[i] * math.sin(rad)
            points.append((x, y))

        r = 12
        for i, (px, py) in enumerate(points):
            self.canvas.coords(self.rotors[i], px - r, py - r, px + r, py + r)

            # label offset (alternate side so they don't overlap)
            ox = 20 if i % 2 == 0 else -28
            oy = -22 if i % 2 == 0 else 18
            self.canvas.coords(self.angle_labels[i], px + ox, py + oy)

            display = self.angles[i]
            is_limit = False
            if self.joint_min[i] is not None:
                if (abs(self.angles[i] - self.joint_min[i]) < 1.0 or
                        abs(self.angles[i] - self.joint_max[i]) < 1.0):
                    is_limit = True
            color = "red" if is_limit else "black"
            self.canvas.itemconfig(self.angle_labels[i],
                                   text=f"{display:.1f}°", fill=color)

        for i in range(4):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.canvas.coords(self.limbs[i], x1, y1, x2, y2)

        # short handle in the direction of R5
        total = accum + self.angles[4]
        rad = math.radians(total)
        hx = points[-1][0] + 16 * math.cos(rad)
        hy = points[-1][1] + 16 * math.sin(rad)
        self.canvas.coords(self.handle_line,
                           points[-1][0], points[-1][1], hx, hy)

    def set_angles(self, new_angles):
        self.angles = list(new_angles)
        for i in range(self.n_joints):
            if self.joint_min[i] is not None:
                self.angles[i] = max(self.joint_min[i],
                                     min(self.joint_max[i], self.angles[i]))
        self._update_kinematics()

    def reset(self):
        self.set_angles(self.default_angles)

    def get_deltas(self):
        return [self.angles[i] - self.default_angles[i] for i in range(5)]


class ArmEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robotic Arm Editor")
        self.root.geometry("1180x680")

        # ---------- Canvas (left) ----------
        self.canvas = tk.Canvas(root, width=700, height=620, bg="#f4f4f6",
                                highlightthickness=1, highlightbackground="#ccc")
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        # Control buttons under the model
        ctrl = tk.Frame(root)
        ctrl.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=6)

        tk.Button(ctrl, text="Reset to Default", command=self.reset_arm, width=16).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Insert Angle Deltas", command=self.insert_deltas, width=18).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Test", command=self.test_driver, width=10).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Clear editor", command=lambda: self.text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=4)
        # ---------- Editor (right) ----------
        right = tk.Frame(root)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(right, text="Robotic arm driver code",
                 font=("Arial", 12, "bold")).pack(anchor="w")

        self.text = scrolledtext.ScrolledText(right, width=42, height=28,
                                              font=("Consolas", 11), undo=True)
        self.text.pack(fill=tk.BOTH, expand=True, pady=4)

        # ---------- Scene ----------
        self.arm = RoboticArm(self.canvas, base_x=280, base_y=320)

        # box: middle between base and collector, left-aligned with base
        self.box = self.canvas.create_rectangle(250, 380, 320, 430,
                                                fill="#4cc9f0", outline="black", width=2,
                                                tags="box")
        self.box_label = self.canvas.create_text(285, 405, text="Box", tags="box")

        # collector below the arm (same idea as original arm_collector)
        self.canvas.create_rectangle(230, 470, 330, 540,
                                     fill="#90be6d", outline="black", width=2)
        self.canvas.create_text(280, 505, text="Collector", font=("Arial", 10, "bold"))

        # mouse state
        self.dragging_joint = None
        self.drag_base = None
        self.dragging_box = False
        self.box_start = None

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.status = tk.Label(root, text="Click a rotor → insert R# 0   |   Drag a limb → rotate joint",
                               anchor="w")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------- helpers ----------
    def _dist_to_segment(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def on_press(self, event):
        # 1. Limb / handle first (drag has priority)
        for i in range(4):
            x1, y1, x2, y2 = self.canvas.coords(self.arm.limbs[i])
            if self._dist_to_segment(event.x, event.y, x1, y1, x2, y2) < 12:
                self.dragging_joint = i
                self.drag_base = (x1, y1)
                return

        hx1, hy1, hx2, hy2 = self.canvas.coords(self.arm.handle_line)
        if self._dist_to_segment(event.x, event.y, hx1, hy1, hx2, hy2) < 12:
            self.dragging_joint = 4
            self.drag_base = (hx1, hy1)
            return

        # 2. Rotor click only if no limb was hit
        for i in range(5):
            coords = self.canvas.coords(self.arm.rotors[i])
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
            if math.hypot(event.x - cx, event.y - cy) < 16:
                self.text.insert(tk.END, f"R{i + 1} 0\n")
                self.text.see(tk.END)
                return

        # 3. Box drag
        bbox = self.canvas.bbox(self.box)
        if bbox and bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]:
            self.dragging_box = True
            self.box_start = (event.x, event.y)

    def on_motion(self, event):
        if self.dragging_joint is not None:
            i = self.dragging_joint
            bx, by = self.drag_base
            dx = event.x - bx
            dy = event.y - by
            if dx == 0 and dy == 0:
                return
            desired_abs = math.degrees(math.atan2(dy, dx))
            prev_accum = sum(self.arm.angles[:i])
            new_angle = desired_abs - prev_accum

            # keep the value reasonably close to the current angle (avoid 360 jumps)
            while new_angle - self.arm.angles[i] > 180:
                new_angle -= 360
            while new_angle - self.arm.angles[i] < -180:
                new_angle += 360

            if self.arm.joint_min[i] is not None:
                new_angle = max(self.arm.joint_min[i],
                                min(self.arm.joint_max[i], new_angle))

            self.arm.angles[i] = new_angle
            self.arm._update_kinematics()
            return

        if self.dragging_box and self.box_start:
            dx = event.x - self.box_start[0]
            dy = event.y - self.box_start[1]
            self.canvas.move("box", dx, dy)
            self.box_start = (event.x, event.y)

    def on_release(self, event):
        self.dragging_joint = None
        self.dragging_box = False
        self.box_start = None

    def reset_arm(self):
        self.arm.reset()

    def insert_deltas(self):
        deltas = self.arm.get_deltas()
        for i, d in enumerate(deltas):
            self.text.insert(tk.END, f"R{i + 1} {d:.1f}\n")
        self.text.see(tk.END)
        
    def test_driver(self):
        """Parse editor, apply relative R commands, animate, then reset after 5 s."""
        if hasattr(self, "_test_after_id"):
            self.root.after_cancel(self._test_after_id)

        raw = self.text.get("1.0", tk.END).splitlines()
        commands = []
        for line in raw:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[0].upper() in ("R1", "R2", "R3", "R4", "R5"):
                try:
                    delta = float(parts[1])
                    if any(t.upper() == "CC" for t in parts[2:]):
                        delta = -abs(delta)
                    idx = int(parts[0][1]) - 1
                    commands.append((idx, delta))
                except ValueError:
                    pass

        # apply relative deltas from current pose
        for idx, delta in commands:
            self.arm.angles[idx] += delta
            if self.arm.joint_min[idx] is not None:
                self.arm.angles[idx] = max(self.arm.joint_min[idx],
                                           min(self.arm.joint_max[idx], self.arm.angles[idx]))
        self.arm._update_kinematics()

        # return to default after 5 seconds
        self._test_after_id = self.root.after(5000, self.reset_arm)


if __name__ == "__main__":
    root = tk.Tk()
    app = ArmEditorApp(root)
    root.mainloop() 
