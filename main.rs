use std::f64::consts::PI;
use std::io::{self, Write, BufWriter};
use std::thread;
use std::time::{Duration, Instant};

// --- Constants ---
const WIDTH: usize = 120;
const HEIGHT: usize = 40;
const PARTICLES: usize = 280;
const LAYERS: usize = 3;

// --- Structs ---
#[derive(Clone, Copy, Debug)]
struct Vec2 {
    x: f64,
    y: f64,
}

impl Vec2 {
    fn new(x: f64, y: f64) -> Self { Self { x, y } }
    fn zero() -> Self { Self { x: 0.0, y: 0.0 } }
    
    fn add(self, other: Vec2) -> Self { Self::new(self.x + other.x, self.y + other.y) }
    fn sub(self, other: Vec2) -> Self { Self::new(self.x - other.x, self.y - other.y) }
    fn mul(self, s: f64) -> Self { Self::new(self.x * s, self.y * s) }
    
    fn len(self) -> f64 { (self.x * self.x + self.y * self.y).sqrt() }
    
    fn norm(self) -> Self {
        let l = self.len();
        if l == 0.0 { Self::zero() } else { Self::new(self.x / l, self.y / l) }
    }
    
    fn rot(self, a: f64) -> Self {
        let c = a.cos();
        let s = a.sin();
        Self::new(self.x * c - self.y * s, self.x * s + self.y * c)
    }
}

#[derive(Clone, Copy)]
struct Particle {
    pos: Vec2,
    vel: Vec2,
    acc: Vec2,
    hue: f64,
    life: f64,
    age: f64,
    layer: f64,
    seed: f64,
}

#[derive(Clone, Copy)]
struct Cell {
    ch: char,
    color: i32,
}

impl Default for Cell {
    fn default() -> Self { Self { ch: ' ', color: 0 } }
}

// --- RNG Helper (LCG) to avoid external crate dependency ---
struct Rng {
    state: u64,
}

impl Rng {
    fn new() -> Self {
        let start = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos() as u64;
        Self { state: start }
    }

    fn next_f64(&mut self) -> f64 {
        self.state = self.state.wrapping_mul(6364136223846793005).wrapping_add(1);
        (self.state >> 33) as f64 / 2147483648.0 // 0.0 to 1.0 approx
    }

    fn range(&mut self, min: f64, max: f64) -> f64 {
        min + (max - min) * self.next_f64()
    }
}

// --- Math Utils ---
fn clampd(v: f64, a: f64, b: f64) -> f64 {
    if v < a { a } else if v > b { b } else { v }
}

fn lerpd(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

fn smoothstep(edge0: f64, edge1: f64, x: f64) -> f64 {
    if edge0 == edge1 { return 0.0; }
    let t = clampd((x - edge0) / (edge1 - edge0), 0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

fn hash_double(x: f64, y: f64, seed: f64) -> f64 {
    let h = x * 37.0 + y * 17.0 + seed * 13.0;
    let s = (h * 12.9898).sin() * 43758.5453;
    s - s.floor()
}

fn noise2d(x: f64, y: f64, seed: f64) -> f64 {
    let xi = x.floor();
    let yi = y.floor();
    let xf = x - xi;
    let yf = y - yi;
    
    let h00 = hash_double(xi + 0.0, yi + 0.0, seed);
    let h10 = hash_double(xi + 1.0, yi + 0.0, seed);
    let h01 = hash_double(xi + 0.0, yi + 1.0, seed);
    let h11 = hash_double(xi + 1.0, yi + 1.0, seed);
    
    let ux = xf * xf * (3.0 - 2.0 * xf);
    let uy = yf * yf * (3.0 - 2.0 * yf);
    
    let a = h00 + (h10 - h00) * ux;
    let b = h01 + (h11 - h01) * ux;
    a + (b - a) * uy
}

// --- Color Utils ---
fn hsv_to_rgb_approx(h: f64, s: f64, v: f64) -> (i32, i32, i32) {
    let c = v * s;
    let hh = h / 60.0;
    let x = c * (1.0 - (hh % 2.0 - 1.0).abs());
    let m = v - c;
    
    let (rr, gg, bb) = if hh < 0.0 { (0.0, 0.0, 0.0) }
    else if hh < 1.0 { (c, x, 0.0) }
    else if hh < 2.0 { (x, c, 0.0) }
    else if hh < 3.0 { (0.0, c, x) }
    else if hh < 4.0 { (0.0, x, c) }
    else if hh < 5.0 { (x, 0.0, c) }
    else { (c, 0.0, x) };
    
    (
        ((rr + m) * 255.0) as i32,
        ((gg + m) * 255.0) as i32,
        ((bb + m) * 255.0) as i32
    )
}

fn rgb_to_ansi_256(r: i32, g: i32, b: i32) -> i32 {
    let ri = r / 51;
    let gi = g / 51;
    let bi = b / 51;
    16 + 36 * ri + 6 * gi + bi
}

fn hue_to_ansi(hue: f64, layer: f64, alpha: f64, palette_shift: f64) -> i32 {
    let h = (hue + palette_shift) % 360.0;
    let s = clampd(0.75 + 0.2 * layer, 0.0, 1.0);
    let v = clampd(0.35 + 0.6 * alpha, 0.0, 1.0);
    let (r, g, b) = hsv_to_rgb_approx(h, s, v);
    rgb_to_ansi_256(r, g, b)
}

fn sample_char(k: f64, layer: f64, flicker: f64) -> char {
    let chars0 = b" .:-=+*#%@";
    let chars1 = b" .,:;irsXA253hMHGS#9B&@";
    let chars2 = b" `'\"^\",:;Il!i><~+_-?][}{1)(|\\/";
    
    let f = clampd(k + layer * 0.4 + flicker * 0.3, 0.0, 1.0);
    
    if layer < 0.33 {
        let idx = (f * (chars2.len() - 1) as f64) as usize;
        chars2[idx] as char
    } else if layer < 0.66 {
        let idx = (f * (chars1.len() - 1) as f64) as usize;
        chars1[idx] as char
    } else {
        let idx = (f * (chars0.len() - 1) as f64) as usize;
        chars0[idx] as char
    }
}

// --- Application State ---
struct App {
    grid: Vec<Vec<Cell>>,
    particles: Vec<Particle>,
    global_time: f64,
    mode_time: f64,
    mode_index: usize,
    frame_count: usize,
    palette_shift: f64,
    rng: Rng,
}

impl App {
    fn new() -> Self {
        let mut rng = Rng::new();
        let mut particles = Vec::with_capacity(PARTICLES);
        for i in 0..PARTICLES {
            particles.push(Self::create_particle(i, &mut rng));
        }

        Self {
            grid: vec![vec![Cell::default(); WIDTH]; HEIGHT],
            particles,
            global_time: 0.0,
            mode_time: 0.0,
            mode_index: 0,
            frame_count: 0,
            palette_shift: 0.0,
            rng,
        }
    }

    fn create_particle(index: usize, rng: &mut Rng) -> Particle {
        let cx = WIDTH as f64 / 2.0;
        let cy = HEIGHT as f64 / 2.0;
        let r = rng.range(0.0, HEIGHT as f64 * 0.45);
        let a = rng.range(0.0, 2.0 * PI);
        let layer = (index % LAYERS) as f64 / LAYERS as f64;
        let life = rng.range(4.0, 18.0);
        
        Particle {
            pos: Vec2::new(cx + a.cos() * r, cy + a.sin() * r * 0.55),
            vel: Vec2::zero(),
            acc: Vec2::zero(),
            hue: rng.range(0.0, 360.0),
            life,
            age: rng.range(0.0, life * 0.2),
            layer,
            seed: rng.range(0.0, 1000.0),
        }
    }

    fn reset_all(&mut self) {
        for i in 0..PARTICLES {
            self.particles[i] = Self::create_particle(i, &mut self.rng);
        }
    }

    fn clear_grid(&mut self) {
        for row in self.grid.iter_mut() {
            for cell in row.iter_mut() {
                cell.ch = ' ';
                cell.color = 0;
            }
        }
    }

    fn put_cell(&mut self, x: i32, y: i32, ch: char, color: i32) {
        if x < 0 || y < 0 || x >= WIDTH as i32 || y >= HEIGHT as i32 { return; }
        let cell = &mut self.grid[y as usize][x as usize];
        if color >= cell.color {
            cell.ch = ch;
            cell.color = color;
        }
    }

    fn update(&mut self, dt: f64) {
        self.global_time += dt;
        self.palette_shift = (self.global_time * 0.21).sin() * 80.0;
        self.mode_time += dt;

        if self.mode_time > 26.0 {
            self.mode_time = 0.0;
            self.mode_index = (self.mode_index + 1) % 3;
            self.reset_all();
        }

        // Update particles
        for i in 0..PARTICLES {
            // We need to copy values needed for update to avoid borrowing issues
            let mut p = self.particles[i]; 
            let t = self.global_time;
            
            // Logic from update_particle
            p.acc = Vec2::zero();
            
            // Apply Field
            let cx = WIDTH as f64 / 2.0;
            let cy = HEIGHT as f64 / 2.0;
            let d = p.pos.sub(Vec2::new(cx, cy));
            let r = d.len() + 0.001;
            
            let (ang, strength, factor) = match self.mode_index {
                0 => {
                    let swirl = (r * 0.12 + t * 0.25).sin();
                    let ang = d.y.atan2(d.x) + 0.9 + swirl * 0.8 + (t * 0.05).sin() * 0.4;
                    let s = ((r * 0.2 - t * 0.5).sin() * 0.5 + 0.5) * (1.0 / (1.0 + r * 0.03)) * (0.7 + 0.4 * (t * 0.7).sin());
                    (ang, s, 1.4)
                },
                1 => {
                     let waves = (r * 0.18 - t * 0.65).sin() + (r * 0.07 + t * 0.3).sin();
                     let ang = d.y.atan2(d.x) + (t * 0.17).sin() * 0.6 + waves * 0.15;
                     let s = ((r * 0.2 - t * 0.5).sin() * 0.5 + 0.5) * (1.0 / (1.0 + r * 0.03)) * (0.7 + 0.4 * (t * 0.7).sin()) * 1.2;
                     (ang, s, 1.0)
                },
                _ => {
                    let lens = smoothstep(0.0, WIDTH as f64 * 0.35, r);
                    let lens2 = 1.0 - smoothstep(WIDTH as f64 * 0.12, WIDTH as f64 * 0.55, r);
                    let swirl = (r * 0.19 + t * 0.7).sin();
                    let ang = d.y.atan2(d.x) + lens * 1.8 + lens2 * -1.2 + (t * 0.4).sin() * 0.4 + swirl * 0.3;
                    let s = ((r * 0.2 - t * 0.5).sin() * 0.5 + 0.5) * (1.0 / (1.0 + r * 0.03)) * (0.7 + 0.4 * (t * 0.7).sin()) * 1.4;
                    (ang, s, 1.3)
                }
            };

            let dir = Vec2::new(ang.cos(), ang.sin());
            let force = dir.mul(strength * (0.4 + p.layer * 0.9) * factor);
            
            let center_vec = Vec2::new(cx, cy).sub(p.pos);
            let rc = center_vec.len() + 0.001;
            let center_pull = center_vec.norm().mul(0.05 / rc);
            
            let n = noise2d(p.pos.x * 0.1, p.pos.y * 0.1, p.seed + t * 0.15);
            let m = noise2d(p.pos.x * 0.05 + 10.0, p.pos.y * 0.05 - 7.0, p.seed + t * 0.2);
            let jitter = Vec2::new((n * 6.28).cos() * 0.1, (m * 6.28).sin() * 0.1);
            
            p.acc = p.acc.add(force).add(center_pull).add(jitter);

            // Apply Orbit
            let offset = (t * 0.13 + p.layer * 5.0).sin();
            let orbit_r = lerpd(HEIGHT as f64 * 0.12, HEIGHT as f64 * 0.4, ((t * 0.05 + p.layer * 3.0).sin() + 1.0) * 0.5);
            let orbit_ang = t * (0.3 + p.layer * 0.7) + p.seed;
            let ring_center = Vec2::new(cx + orbit_ang.cos() * orbit_r * 0.75, cy + (orbit_ang * 1.1).sin() * orbit_r * 0.4);
            let od = ring_center.sub(p.pos);
            let odist = od.len() + 0.001;
            let odir = od.norm().mul(0.25 + 0.6 * (1.0 / (1.0 + odist * 0.2)));
            let tangent = odir.rot(offset * 0.7);
            p.acc = p.acc.add(tangent);

            // Apply Noise Orbit
            let scale = 0.12 + 0.05 * p.layer;
            let nx = p.pos.x * scale;
            let ny = p.pos.y * scale;
            let na = noise2d(nx, ny, p.seed + t * 0.17) * 6.28318;
            let nb = noise2d(nx + 17.0, ny + 9.0, p.seed - t * 0.21) * 6.28318;
            let f1 = Vec2::new(na.cos(), na.sin());
            let f2 = Vec2::new(nb.cos(), nb.sin());
            p.acc = p.acc.add(f1.mul(0.3).add(f2.mul(0.25)));

            // Integrate
            p.vel = p.vel.add(p.acc.mul(dt * 7.0 * 0.7));
            let max_speed = 2.0 + p.layer * 3.0;
            if p.vel.len() > max_speed {
                p.vel = p.vel.norm().mul(max_speed);
            }
            p.pos = p.pos.add(p.vel.mul(dt * 7.0));

            // Bounds & Age
            if p.pos.x < -10.0 || p.pos.x > WIDTH as f64 + 10.0 || p.pos.y < -10.0 || p.pos.y > HEIGHT as f64 + 10.0 {
                p = Self::create_particle(i, &mut self.rng);
            }
            p.age += dt * 7.0 * (0.8 + p.layer * 0.7);
            if p.age > p.life {
                p = Self::create_particle(i, &mut self.rng);
            }

            self.particles[i] = p;
        }
    }

    fn draw(&mut self) {
        self.clear_grid();
        let t = self.global_time;

        // Draw Trails
        for i in 0..PARTICLES {
            let p = self.particles[i];
            let trail_k = 1.0 - smoothstep(0.0, p.life * 0.4, p.age);
            let steps = 3;
            for s in 1..=steps {
                let u = s as f64 / (steps + 1) as f64;
                let pos = p.pos.sub(p.vel.mul(u * 0.9));
                let alpha = trail_k * (1.0 - u * 0.9);
                let color = hue_to_ansi(p.hue + t * (1.0 + p.layer * 5.0), p.layer * 0.6, alpha, self.palette_shift);
                let ch = sample_char(alpha * 0.8, p.layer * 0.6, u);
                self.put_cell(pos.x.round() as i32, pos.y.round() as i32, ch, color);
            }
        }

        // Draw Core
        let cx = WIDTH as f64 / 2.0;
        let cy = HEIGHT as f64 / 2.0;
        let r = HEIGHT as f64 * 0.12 + (t * 0.6).sin() * HEIGHT as f64 * 0.025;
        let steps = (r * 8.0) as i32;
        for i in 0..steps {
            let a = i as f64 / steps as f64 * 2.0 * PI;
            let rr = r * (0.8 + 0.4 * (t * 0.9 + i as f64 * 0.3).sin());
            let x = cx + a.cos() * rr;
            let y = cy + a.sin() * rr * 0.7;
            let k = smoothstep(0.0, HEIGHT as f64 * 0.2, rr);
            let alpha = 1.0 - k;
            let color = hue_to_ansi(180.0 + (t * 0.4).sin() * 80.0, 0.8, alpha, self.palette_shift);
            let ch = sample_char(alpha, 0.8, 0.5);
            self.put_cell(x.round() as i32, y.round() as i32, ch, color);
        }

        // Draw Rings
        for ring in 0..3 {
            let rf = ring as f64;
            let base_r = HEIGHT as f64 * (0.12 + 0.14 * rf);
            let wobble = (t * (0.4 + rf * 0.13) + rf * 2.0).sin() * HEIGHT as f64 * 0.03;
            let r = base_r + wobble;
            let r_steps = (r * 7.0) as i32;
            for i in 0..r_steps {
                let a = i as f64 / r_steps as f64 * 2.0 * PI;
                let x = cx + a.cos() * r * (1.04 + rf * 0.05);
                let y = cy + a.sin() * r * (0.7 + rf * 0.08);
                let k = smoothstep(HEIGHT as f64 * 0.05, HEIGHT as f64 * 0.55, r);
                let alpha = 0.35 + (1.0 - k) * 0.5;
                let color = hue_to_ansi(40.0 + rf * 90.0 + t * 3.0, 0.4 + rf * 0.3, alpha, self.palette_shift);
                let ch = sample_char(alpha, 0.4 + rf * 0.3, 0.5);
                self.put_cell(x.round() as i32, y.round() as i32, ch, color);
            }
        }

        // Draw Wave Text
        let text = "emergent orbit";
        let tlen = text.len();
        let base_y = HEIGHT as f64 - 4.0;
        let span = WIDTH as f64 * 0.66;
        let start_x = (WIDTH as f64 - span) * 0.5;
        for (i, ch_val) in text.chars().enumerate() {
            let u = i as f64 / (tlen - 1) as f64;
            let x = start_x + u * span;
            let phase = t * 0.7 + u * 6.0;
            let dy = phase.sin() * 2.0 + (phase * 0.5).sin() * 1.5;
            let y = base_y + dy;
            let w = ((phase * 1.7).sin() + 1.0) * 0.5;
            let alpha = 0.4 + w * 0.6;
            let color = hue_to_ansi(300.0 + w * 120.0, 0.9, alpha, self.palette_shift);
            self.put_cell(x.round() as i32, y.round() as i32, ch_val, color);
            self.put_cell(x.round() as i32, y.round() as i32 - 1, '.', color);
        }

        // Draw Mode
        let names = ["spiral field", "ring waves", "lens flow"];
        let label = names[self.mode_index];
        let llen = label.len();
        for (i, ch) in label.chars().enumerate() {
             let k = i as f64 / (llen - 1) as f64;
             let alpha = 0.6 + 0.4 * (t * 2.0 + k * 3.0).sin();
             let color = hue_to_ansi(200.0 + k * 80.0, 0.3, alpha, self.palette_shift);
             self.put_cell(2 + i as i32, 1, ch, color);
        }

        // Draw Frame Count
        let frame_str = format!("frame {:06}", self.frame_count);
        let fcx = WIDTH - 18;
        for (i, ch) in frame_str.chars().enumerate() {
             let color = hue_to_ansi(120.0 + i as f64 * 10.0, 0.5, 0.7, self.palette_shift);
             self.put_cell((fcx + i) as i32, 1, ch, color);
        }

        // Draw Particles
        for i in 0..PARTICLES {
            let p = self.particles[i];
            let fade_in = smoothstep(0.0, p.life * 0.2, p.age);
            let fade_out = 1.0 - smoothstep(p.life * 0.3, p.life, p.age);
            let energy = fade_in * fade_out;
            let glow = smoothstep(0.0, 1.0, energy);
            let flicker = (t * 6.0 + p.seed * 4.0).sin() * 0.5 + 0.5;
            let alpha = clampd(glow * (0.3 + flicker * 0.9), 0.0, 1.0);
            let gx = p.pos.x.round() as i32;
            let gy = p.pos.y.round() as i32;
            let color = hue_to_ansi(p.hue + t * (4.0 + p.layer * 20.0), p.layer, alpha, self.palette_shift);
            let ch = sample_char(alpha, p.layer, flicker);
            self.put_cell(gx, gy, ch, color);

            // Glow
            for dy in -1..=1 {
                for dx in -1..=1 {
                    if dx == 0 && dy == 0 { continue; }
                    let falloff = 1.0 / (1.0 + (dx * dx + dy * dy) as f64);
                    let aa = alpha * falloff * 0.7;
                    let cc = hue_to_ansi(p.hue + t * 2.0, p.layer * 0.6, aa, self.palette_shift);
                    let ch2 = sample_char(aa * 0.8, p.layer * 0.7, flicker * 0.4);
                    if aa > 0.05 {
                        self.put_cell(gx + dx, gy + dy, ch2, cc);
                    }
                }
            }
        }
    }

    fn flush(&mut self, writer: &mut impl Write) -> io::Result<()> {
        write!(writer, "\x1b[H")?;
        let mut last_color = -1;

        for y in 0..HEIGHT {
            for x in 0..WIDTH {
                let c = &self.grid[y][x];
                if c.color <= 0 {
                    if last_color != 0 {
                        write!(writer, "\x1b[0m")?;
                        last_color = 0;
                    }
                    write!(writer, " ")?;
                } else {
                    if c.color != last_color {
                        write!(writer, "\x1b[38;5;{}m", c.color)?;
                        last_color = c.color;
                    }
                    write!(writer, "{}", c.ch)?;
                }
            }
            if last_color != 0 {
                write!(writer, "\x1b[0m")?;
                last_color = 0;
            }
            write!(writer, "\n")?;
        }
        write!(writer, "\x1b[0m")?;
        writer.flush()
    }
}

// --- Main Entry Point ---
fn main() {
    let mut app = App::new();
    let stdout = io::stdout();
    let mut handle = BufWriter::new(stdout.lock());
    
    // Clear screen once
    write!(handle, "\x1b[2J\x1b[H").unwrap();

    let mut last_time = Instant::now();

    loop {
        let current_time = Instant::now();
        let dt_dur = current_time.duration_since(last_time);
        last_time = current_time;
        
        let mut dt = dt_dur.as_secs_f64();
        if dt <= 0.0 { dt = 0.016; }
        if dt > 0.1 { dt = 0.1; }

        app.update(dt);
        app.draw();
        
        if let Err(_) = app.flush(&mut handle) {
            break; 
        }
        
        app.frame_count += 1;
        
        if app.frame_count > 0 && app.frame_count % 9000 == 0 {
            app.reset_all();
        }

        thread::sleep(Duration::from_millis(33));
    }
}
