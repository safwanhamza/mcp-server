#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

#define WIDTH 120
#define HEIGHT 40
#define PARTICLES 280
#define LAYERS 3
#define PI 3.14159265358979323846

typedef struct
{
    double x;
    double y;
} Vec2;

typedef struct
{
    Vec2 pos;
    Vec2 vel;
    Vec2 acc;
    double hue;
    double life;
    double age;
    double layer;
    double seed;
} Particle;

typedef struct
{
    char ch;
    int color;
} Cell;

static Particle particles[PARTICLES];
static Cell grid[HEIGHT][WIDTH];

static double global_time = 0.0;
static double mode_time = 0.0;
static int mode_index = 0;
static int frame_count = 0;
static double palette_shift = 0.0;

double frand01()
{
    return rand() / (double)RAND_MAX;
}

double frand(double min, double max)
{
    return min + (max - min) * frand01();
}

double clampd(double v, double a, double b)
{
    if (v < a) return a;
    if (v > b) return b;
    return v;
}

double lerpd(double a, double b, double t)
{
    return a + (b - a) * t;
}

Vec2 vec(double x, double y)
{
    Vec2 v;
    v.x = x;
    v.y = y;
    return v;
}

Vec2 vec_add(Vec2 a, Vec2 b)
{
    Vec2 v;
    v.x = a.x + b.x;
    v.y = a.y + b.y;
    return v;
}

Vec2 vec_sub(Vec2 a, Vec2 b)
{
    Vec2 v;
    v.x = a.x - b.x;
    v.y = a.y - b.y;
    return v;
}

Vec2 vec_mul(Vec2 a, double s)
{
    Vec2 v;
    v.x = a.x * s;
    v.y = a.y * s;
    return v;
}

double vec_len(Vec2 v)
{
    return sqrt(v.x * v.x + v.y * v.y);
}

Vec2 vec_norm(Vec2 v)
{
    double l = vec_len(v);
    if (l == 0.0)
    {
        return vec(0.0, 0.0);
    }
    return vec(v.x / l, v.y / l);
}

Vec2 vec_rot(Vec2 v, double a)
{
    double c = cos(a);
    double s = sin(a);
    return vec(v.x * c - v.y * s, v.x * s + v.y * c);
}

double ease_in_out(double t)
{
    if (t < 0.5)
    {
        return 2.0 * t * t;
    }
    else
    {
        return -1.0 + (4.0 - 2.0 * t) * t;
    }
}

double smoothstep(double edge0, double edge1, double x)
{
    double t;
    if (edge0 == edge1)
    {
        return 0.0;
    }
    t = (x - edge0) / (edge1 - edge0);
    t = clampd(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

double hash_double(double x, double y, double seed)
{
    double h = x * 37.0 + y * 17.0 + seed * 13.0;
    double s = sin(h * 12.9898) * 43758.5453;
    return s - floor(s);
}

double noise2d(double x, double y, double seed)
{
    double xi = floor(x);
    double yi = floor(y);
    double xf = x - xi;
    double yf = y - yi;
    double h00 = hash_double(xi + 0.0, yi + 0.0, seed);
    double h10 = hash_double(xi + 1.0, yi + 0.0, seed);
    double h01 = hash_double(xi + 0.0, yi + 1.0, seed);
    double h11 = hash_double(xi + 1.0, yi + 1.0, seed);
    double ux = xf * xf * (3.0 - 2.0 * xf);
    double uy = yf * yf * (3.0 - 2.0 * yf);
    double a = h00 + (h10 - h00) * ux;
    double b = h01 + (h11 - h01) * ux;
    return a + (b - a) * uy;
}

void clear_grid()
{
    int y;
    int x;
    for (y = 0; y < HEIGHT; y++)
    {
        for (x = 0; x < WIDTH; x++)
        {
            grid[y][x].ch = ' ';
            grid[y][x].color = 0;
        }
    }
}

void put_cell(int x, int y, char ch, int color)
{
    if (x < 0) return;
    if (y < 0) return;
    if (x >= WIDTH) return;
    if (y >= HEIGHT) return;
    if (color >= grid[y][x].color)
    {
        grid[y][x].ch = ch;
        grid[y][x].color = color;
    }
}

void hsv_to_rgb_approx(double h, double s, double v, int *r, int *g, int *b)
{
    double c = v * s;
    double hh = h / 60.0;
    double x = c * (1.0 - fabs(fmod(hh, 2.0) - 1.0));
    double m = v - c;
    double rr;
    double gg;
    double bb;
    if (hh < 0.0)
    {
        hh = 0.0;
    }
    if (hh < 1.0)
    {
        rr = c; gg = x; bb = 0.0;
    }
    else if (hh < 2.0)
    {
        rr = x; gg = c; bb = 0.0;
    }
    else if (hh < 3.0)
    {
        rr = 0.0; gg = c; bb = x;
    }
    else if (hh < 4.0)
    {
        rr = 0.0; gg = x; bb = c;
    }
    else if (hh < 5.0)
    {
        rr = x; gg = 0.0; bb = c;
    }
    else
    {
        rr = c; gg = 0.0; bb = x;
    }
    rr += m;
    gg += m;
    bb += m;
    *r = (int)(rr * 255.0);
    *g = (int)(gg * 255.0);
    *b = (int)(bb * 255.0);
}

int rgb_to_ansi_256(int r, int g, int b)
{
    int ri = r / 51;
    int gi = g / 51;
    int bi = b / 51;
    int code = 16 + 36 * ri + 6 * gi + bi;
    return code;
}

int hue_to_ansi(double hue, double layer, double alpha)
{
    double h = fmod(hue + palette_shift, 360.0);
    double s = 0.75 + 0.2 * layer;
    double v = 0.35 + 0.6 * alpha;
    int r;
    int g;
    int b;
    if (s > 1.0) s = 1.0;
    if (s < 0.0) s = 0.0;
    if (v > 1.0) v = 1.0;
    if (v < 0.0) v = 0.0;
    hsv_to_rgb_approx(h, s, v, &r, &g, &b);
    return rgb_to_ansi_256(r, g, b);
}

void flush_grid()
{
    int y;
    int x;
    int last_color = -1;
    printf("\x1b[H");
    for (y = 0; y < HEIGHT; y++)
    {
        for (x = 0; x < WIDTH; x++)
        {
            Cell c = grid[y][x];
            if (c.color <= 0)
            {
                if (last_color != 0)
                {
                    printf("\x1b[0m");
                    last_color = 0;
                }
                putchar(' ');
            }
            else
            {
                if (c.color != last_color)
                {
                    printf("\x1b[38;5;%dm", c.color);
                    last_color = c.color;
                }
                putchar(c.ch);
            }
        }
        if (last_color != 0)
        {
            printf("\x1b[0m");
            last_color = 0;
        }
        putchar('\n');
    }
    printf("\x1b[0m");
    fflush(stdout);
}

void sleep_ms(int ms)
{
#ifdef _WIN32
    Sleep(ms);
#else
    usleep(ms * 1000);
#endif
}

void init_particle(Particle *p, int index)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    double r = frand(0.0, (double)(HEIGHT) * 0.45);
    double a = frand(0.0, 2.0 * PI);
    double layer = (double)(index % LAYERS) / (double)LAYERS;
    double life = frand(4.0, 18.0);
    p->pos = vec(cx + cos(a) * r, cy + sin(a) * r * 0.55);
    p->vel = vec(0.0, 0.0);
    p->acc = vec(0.0, 0.0);
    p->hue = frand(0.0, 360.0);
    p->life = life;
    p->age = frand(0.0, life * 0.2);
    p->layer = layer;
    p->seed = frand(0.0, 1000.0);
}

void init_particles()
{
    int i;
    for (i = 0; i < PARTICLES; i++)
    {
        init_particle(&particles[i], i);
    }
}

void reset_all()
{
    init_particles();
}

double field_angle_spiral(Vec2 p, double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    Vec2 d = vec_sub(p, vec(cx, cy));
    double r = vec_len(d) + 0.001;
    double ang = atan2(d.y, d.x);
    double swirl = sin(r * 0.12 + t * 0.25);
    double offset = 0.9 + swirl * 0.8;
    double bend = sin(t * 0.05) * 0.4;
    double result = ang + offset + bend;
    return result;
}

double field_angle_rings(Vec2 p, double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    Vec2 d = vec_sub(p, vec(cx, cy));
    double r = vec_len(d);
    double base = atan2(d.y, d.x);
    double waves = sin(r * 0.18 - t * 0.65) + sin(r * 0.07 + t * 0.3);
    double twist = sin(t * 0.17) * 0.6;
    double result = base + twist + waves * 0.15;
    return result;
}

double field_angle_lensing(Vec2 p, double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    Vec2 d = vec_sub(p, vec(cx, cy));
    double r = vec_len(d);
    double base = atan2(d.y, d.x);
    double lens = smoothstep(0.0, (double)WIDTH * 0.35, r);
    double lens2 = 1.0 - smoothstep((double)WIDTH * 0.12, (double)WIDTH * 0.55, r);
    double pulse = sin(t * 0.4) * 0.4;
    double swirl = sin(r * 0.19 + t * 0.7);
    double result = base + lens * 1.8 + lens2 * (-1.2) + pulse + swirl * 0.3;
    return result;
}

double field_strength(Vec2 p, double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    Vec2 d = vec_sub(p, vec(cx, cy));
    double r = vec_len(d) + 0.001;
    double wave = sin(r * 0.2 - t * 0.5) * 0.5 + 0.5;
    double fall = 1.0 / (1.0 + r * 0.03);
    double pulse = 0.7 + 0.4 * sin(t * 0.7);
    double result = wave * fall * pulse;
    return result;
}

void apply_field(Particle *p, double dt, double t)
{
    Vec2 pos = p->pos;
    double factor = 1.0;
    double ang;
    double strength;
    if (mode_index == 0)
    {
        ang = field_angle_spiral(pos, t);
        strength = field_strength(pos, t);
        factor = 1.4;
    }
    else if (mode_index == 1)
    {
        ang = field_angle_rings(pos, t);
        strength = field_strength(pos, t) * 1.2;
        factor = 1.0;
    }
    else
    {
        ang = field_angle_lensing(pos, t);
        strength = field_strength(pos, t) * 1.4;
        factor = 1.3;
    }
    Vec2 dir = vec(cos(ang), sin(ang));
    Vec2 f = vec_mul(dir, strength * (0.4 + p->layer * 0.9) * factor);
    Vec2 cx = vec(WIDTH / 2.0, HEIGHT / 2.0);
    Vec2 towards_center = vec_sub(cx, pos);
    double rc = vec_len(towards_center) + 0.001;
    towards_center = vec_mul(vec_norm(towards_center), 0.05 / rc);
    Vec2 jitter;
    double n = noise2d(pos.x * 0.1, pos.y * 0.1, p->seed + t * 0.15);
    double m = noise2d(pos.x * 0.05 + 10.0, pos.y * 0.05 - 7.0, p->seed + t * 0.2);
    jitter = vec(cos(n * 6.28) * 0.1, sin(m * 6.28) * 0.1);
    Vec2 total = vec_add(f, towards_center);
    total = vec_add(total, jitter);
    p->acc = vec_add(p->acc, total);
}

void apply_orbit(Particle *p, double dt, double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    double offset = sin(t * 0.13 + p->layer * 5.0);
    double orbit_r = lerpd((double)HEIGHT * 0.12, (double)HEIGHT * 0.4, (sin(t * 0.05 + p->layer * 3.0) + 1.0) * 0.5);
    double angle = global_time * (0.3 + p->layer * 0.7) + p->seed;
    Vec2 ring_center = vec(cx + cos(angle) * orbit_r * 0.75, cy + sin(angle * 1.1) * orbit_r * 0.4);
    Vec2 d = vec_sub(ring_center, p->pos);
    double dist = vec_len(d) + 0.001;
    Vec2 dir = vec_mul(vec_norm(d), 0.25 + 0.6 * (1.0 / (1.0 + dist * 0.2)));
    Vec2 tangent = vec_rot(dir, offset * 0.7);
    p->acc = vec_add(p->acc, tangent);
}

void apply_noise_orbit(Particle *p, double dt, double t)
{
    double scale = 0.12 + 0.05 * p->layer;
    double nx = p->pos.x * scale;
    double ny = p->pos.y * scale;
    double a = noise2d(nx, ny, p->seed + t * 0.17) * 6.28318;
    double b = noise2d(nx + 17.0, ny + 9.0, p->seed - t * 0.21) * 6.28318;
    Vec2 f1 = vec(cos(a), sin(a));
    Vec2 f2 = vec(cos(b), sin(b));
    Vec2 f = vec_add(vec_mul(f1, 0.3), vec_mul(f2, 0.25));
    p->acc = vec_add(p->acc, f);
}

void update_particle(Particle *p, double dt, double t)
{
    p->acc = vec(0.0, 0.0);
    apply_field(p, dt, t);
    apply_orbit(p, dt, t);
    apply_noise_orbit(p, dt, t);
    p->vel = vec_add(p->vel, vec_mul(p->acc, dt * 0.7));
    double max_speed = 2.0 + p->layer * 3.0;
    double speed = vec_len(p->vel);
    if (speed > max_speed)
    {
        p->vel = vec_mul(vec_norm(p->vel), max_speed);
    }
    p->pos = vec_add(p->pos, vec_mul(p->vel, dt));
    if (p->pos.x < -10.0 || p->pos.x > WIDTH + 10.0 || p->pos.y < -10.0 || p->pos.y > HEIGHT + 10.0)
    {
        init_particle(p, (int)(p - particles));
    }
    p->age += dt * (0.8 + p->layer * 0.7);
    if (p->age > p->life)
    {
        init_particle(p, (int)(p - particles));
    }
}

char sample_char(double k, double layer, double flicker)
{
    const char *chars0 = " .:-=+*#%@";
    const char *chars1 = " .,:;irsXA253hMHGS#9B&@";
    const char *chars2 = " `'\"^\",:;Il!i><~+_-?][}{1)(|\\/";
    double s = smoothstep(0.0, 1.0, k);
    int len0 = (int)strlen(chars0);
    int len1 = (int)strlen(chars1);
    int len2 = (int)strlen(chars2);
    double f = clampd(k + layer * 0.4 + flicker * 0.3, 0.0, 1.0);
    int index0 = (int)(f * (len0 - 1));
    int index1 = (int)(f * (len1 - 1));
    int index2 = (int)(f * (len2 - 1));
    if (layer < 0.33)
    {
        return chars2[index2];
    }
    else if (layer < 0.66)
    {
        return chars1[index1];
    }
    else
    {
        return chars0[index0];
    }
}

void draw_particle(Particle *p, double t)
{
    double fade_in = smoothstep(0.0, p->life * 0.2, p->age);
    double fade_out = 1.0 - smoothstep(p->life * 0.3, p->life, p->age);
    double energy = fade_in * fade_out;
    double glow = smoothstep(0.0, 1.0, energy);
    double flicker = sin(t * 6.0 + p->seed * 4.0) * 0.5 + 0.5;
    double alpha = clampd(glow * (0.3 + flicker * 0.9), 0.0, 1.0);
    int gx = (int)round(p->pos.x);
    int gy = (int)round(p->pos.y);
    int color = hue_to_ansi(p->hue + t * (4.0 + p->layer * 20.0), p->layer, alpha);
    char c = sample_char(alpha, p->layer, flicker);
    put_cell(gx, gy, c, color);
    {
        int dx;
        int dy;
        for (dy = -1; dy <= 1; dy++)
        {
            for (dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dy == 0) continue;
                double falloff = 1.0 / (1.0 + dx * dx + dy * dy);
                double aa = alpha * falloff * 0.7;
                int cc = hue_to_ansi(p->hue + t * 2.0, p->layer * 0.6, aa);
                char ch2 = sample_char(aa * 0.8, p->layer * 0.7, flicker * 0.4);
                if (aa > 0.05)
                {
                    put_cell(gx + dx, gy + dy, ch2, cc);
                }
            }
        }
    }
}

void draw_core(double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    double r = (double)HEIGHT * 0.12 + sin(t * 0.6) * (double)HEIGHT * 0.025;
    int steps = (int)(r * 8.0);
    int i;
    for (i = 0; i < steps; i++)
    {
        double a = (double)i / (double)steps * 2.0 * PI;
        double rr = r * (0.8 + 0.4 * sin(t * 0.9 + i * 0.3));
        double x = cx + cos(a) * rr;
        double y = cy + sin(a) * rr * 0.7;
        double k = smoothstep(0.0, (double)HEIGHT * 0.2, rr);
        double alpha = 1.0 - k;
        int color = hue_to_ansi(180.0 + sin(t * 0.4) * 80.0, 0.8, alpha);
        char ch = sample_char(alpha, 0.8, 0.5);
        put_cell((int)round(x), (int)round(y), ch, color);
    }
}

void draw_wave_text(double t)
{
    const char *text = "emergent orbit";
    int len = (int)strlen(text);
    double base_y = (double)(HEIGHT - 4);
    double span = (double)WIDTH * 0.66;
    double start_x = (WIDTH - span) * 0.5;
    int i;
    for (i = 0; i < len; i++)
    {
        double u = (double)i / (double)(len - 1);
        double x = start_x + u * span;
        double phase = t * 0.7 + u * 6.0;
        double dy = sin(phase) * 2.0 + sin(phase * 0.5) * 1.5;
        double y = base_y + dy;
        double w = (sin(phase * 1.7) + 1.0) * 0.5;
        double alpha = 0.4 + w * 0.6;
        int color = hue_to_ansi(300.0 + w * 120.0, 0.9, alpha);
        char ch = text[i];
        put_cell((int)round(x), (int)round(y), ch, color);
        put_cell((int)round(x), (int)round(y) - 1, '.', color);
    }
}

void draw_rings(double t)
{
    double cx = WIDTH / 2.0;
    double cy = HEIGHT / 2.0;
    int ring;
    for (ring = 0; ring < 3; ring++)
    {
        double base_r = (double)HEIGHT * (0.12 + 0.14 * ring);
        double wobble = sin(t * (0.4 + ring * 0.13) + ring * 2.0) * (double)HEIGHT * 0.03;
        double r = base_r + wobble;
        int steps = (int)(r * 7.0);
        int i;
        for (i = 0; i < steps; i++)
        {
            double a = (double)i / (double)steps * 2.0 * PI;
            double x = cx + cos(a) * r * (1.04 + ring * 0.05);
            double y = cy + sin(a) * r * (0.7 + ring * 0.08);
            double k = smoothstep((double)HEIGHT * 0.05, (double)HEIGHT * 0.55, r);
            double alpha = 0.35 + (1.0 - k) * 0.5;
            int color = hue_to_ansi(40.0 + ring * 90.0 + t * 3.0, 0.4 + ring * 0.3, alpha);
            char ch = sample_char(alpha, 0.4 + ring * 0.3, 0.5);
            put_cell((int)round(x), (int)round(y), ch, color);
        }
    }
}

void draw_trails(double t)
{
    int i;
    for (i = 0; i < PARTICLES; i++)
    {
        Particle *p = &particles[i];
        double trail_k = 1.0 - smoothstep(0.0, p->life * 0.4, p->age);
        int trail_steps = 3;
        int s;
        for (s = 1; s <= trail_steps; s++)
        {
            double u = (double)s / (double)(trail_steps + 1);
            Vec2 pos = vec_sub(p->pos, vec_mul(p->vel, u * 0.9));
            double alpha = trail_k * (1.0 - u * 0.9);
            int gx = (int)round(pos.x);
            int gy = (int)round(pos.y);
            int color = hue_to_ansi(p->hue + t * (1.0 + p->layer * 5.0), p->layer * 0.6, alpha);
            char ch = sample_char(alpha * 0.8, p->layer * 0.6, u);
            put_cell(gx, gy, ch, color);
        }
    }
}

void draw_mode_indicator(double t)
{
    const char *names[] = { "spiral field", "ring waves", "lens flow" };
    const int modes = 3;
    const char *label = names[mode_index % modes];
    int len = (int)strlen(label);
    int x0 = 2;
    int y0 = 1;
    int i;
    for (i = 0; i < len; i++)
    {
        double k = (double)i / (double)(len - 1);
        double alpha = 0.6 + 0.4 * sin(t * 2.0 + k * 3.0);
        int color = hue_to_ansi(200.0 + k * 80.0, 0.3, alpha);
        put_cell(x0 + i, y0, label[i], color);
    }
    {
        char buf[64];
        int cx = WIDTH - 18;
        int cy = 1;
        int fps = (int)round(1.0 / (0.016 + 0.0));
        snprintf(buf, sizeof(buf), "frame %06d", frame_count);
        for (i = 0; buf[i] != '\0'; i++)
        {
            int color = hue_to_ansi(120.0 + i * 10.0, 0.5, 0.7);
            put_cell(cx + i, cy, buf[i], color);
        }
    }
}

void maybe_change_mode(double dt)
{
    mode_time += dt;
    if (mode_time > 26.0)
    {
        mode_time = 0.0;
        mode_index = (mode_index + 1) % 3;
        reset_all();
    }
}

int main()
{
    int running = 1;
    double last_time;
    double current_time;
    double dt;
    int i;
    srand((unsigned int)time(NULL));
    printf("\x1b[2J\x1b[H");
    setvbuf(stdout, NULL, _IOFBF, 0);
    init_particles();
    last_time = (double)clock() / (double)CLOCKS_PER_SEC;
    while (running)
    {
        current_time = (double)clock() / (double)CLOCKS_PER_SEC;
        dt = current_time - last_time;
        if (dt <= 0.0)
        {
            dt = 0.016;
        }
        if (dt > 0.1)
        {
            dt = 0.1;
        }
        last_time = current_time;
        global_time += dt;
        palette_shift = sin(global_time * 0.21) * 80.0;
        maybe_change_mode(dt);
        clear_grid();
        for (i = 0; i < PARTICLES; i++)
        {
            update_particle(&particles[i], dt * 7.0, global_time);
        }
        draw_trails(global_time);
        draw_core(global_time);
        draw_rings(global_time);
        draw_wave_text(global_time);
        draw_mode_indicator(global_time);
        for (i = 0; i < PARTICLES; i++)
        {
            draw_particle(&particles[i], global_time);
        }
        flush_grid();
        frame_count++;
        sleep_ms(33);
        if (frame_count > 0 && frame_count % 9000 == 0)
        {
            reset_all();
        }
    }
    return 0;
}
