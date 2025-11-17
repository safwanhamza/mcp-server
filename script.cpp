#include <iostream>
#include <vector>
#include <string>
#include <random>
#include <chrono>
#include <algorithm>
#include <functional>
#include <map>
#include <set>
#include <queue>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <fstream>
#include <memory>
#include <limits>

using namespace std;

struct Vec2
{
    int x;
    int y;

    Vec2() : x(0), y(0) {}
    Vec2(int x_, int y_) : x(x_), y(y_) {}

    bool operator==(const Vec2 &other) const
    {
        return x == other.x && y == other.y;
    }

    bool operator!=(const Vec2 &other) const
    {
        return !(*this == other);
    }

    Vec2 operator+(const Vec2 &other) const
    {
        return Vec2(x + other.x, y + other.y);
    }

    Vec2 operator-(const Vec2 &other) const
    {
        return Vec2(x - other.x, y - other.y);
    }

    Vec2 &operator+=(const Vec2 &other)
    {
        x += other.x;
        y += other.y;
        return *this;
    }

    Vec2 &operator-=(const Vec2 &other)
    {
        x -= other.x;
        y -= other.y;
        return *this;
    }
};

struct Vec2Hash
{
    size_t operator()(const Vec2 &v) const
    {
        return (static_cast<size_t>(v.x) << 32) ^ static_cast<size_t>(v.y);
    }
};

ostream &operator<<(ostream &os, const Vec2 &v)
{
    os << "(" << v.x << "," << v.y << ")";
    return os;
}

double length(const Vec2 &v)
{
    return std::sqrt(static_cast<double>(v.x * v.x + v.y * v.y));
}

struct RNG
{
    mt19937_64 engine;

    RNG()
    {
        seedWithTime();
    }

    void seedWithTime()
    {
        auto now = chrono::high_resolution_clock::now().time_since_epoch().count();
        engine.seed(static_cast<uint64_t>(now));
    }

    void seed(uint64_t value)
    {
        engine.seed(value);
    }

    int intInRange(int a, int b)
    {
        uniform_int_distribution<int> dist(a, b);
        return dist(engine);
    }

    double real01()
    {
        uniform_real_distribution<double> dist(0.0, 1.0);
        return dist(engine);
    }

    double realRange(double a, double b)
    {
        uniform_real_distribution<double> dist(a, b);
        return dist(engine);
    }

    bool chance(double p)
    {
        return real01() < p;
    }

    template <typename T>
    const T &choice(const vector<T> &v)
    {
        if (v.empty())
        {
            throw runtime_error("choice on empty vector");
        }
        int idx = intInRange(0, static_cast<int>(v.size()) - 1);
        return v[idx];
    }
};

enum class CellType
{
    Empty,
    Wall,
    MarkerA,
    MarkerB,
    MarkerC,
    Source,
    Sink,
    Trail,
    Signal
};

char cellTypeToChar(CellType t)
{
    switch (t)
    {
    case CellType::Empty:
        return ' ';
    case CellType::Wall:
        return '#';
    case CellType::MarkerA:
        return 'a';
    case CellType::MarkerB:
        return 'b';
    case CellType::MarkerC:
        return 'c';
    case CellType::Source:
        return 'S';
    case CellType::Sink:
        return 'K';
    case CellType::Trail:
        return '.';
    case CellType::Signal:
        return '*';
    default:
        return '?';
    }
}

struct Cell
{
    CellType type;
    double value1;
    double value2;

    Cell() : type(CellType::Empty), value1(0.0), value2(0.0) {}
};

class Grid
{
    int width;
    int height;
    vector<Cell> data;

public:
    Grid(int w = 0, int h = 0)
        : width(w), height(h), data(static_cast<size_t>(w * h))
    {
    }

    void resize(int w, int h)
    {
        width = w;
        height = h;
        data.assign(static_cast<size_t>(w * h), Cell{});
    }

    int getWidth() const
    {
        return width;
    }

    int getHeight() const
    {
        return height;
    }

    bool inBounds(const Vec2 &p) const
    {
        return p.x >= 0 && p.y >= 0 && p.x < width && p.y < height;
    }

    Cell &at(const Vec2 &p)
    {
        return data[static_cast<size_t>(p.y * width + p.x)];
    }

    const Cell &at(const Vec2 &p) const
    {
        return data[static_cast<size_t>(p.y * width + p.x)];
    }

    void fill(CellType t)
    {
        for (auto &c : data)
        {
            c.type = t;
            c.value1 = 0.0;
            c.value2 = 0.0;
        }
    }

    void forEach(function<void(const Vec2 &, Cell &)> fn)
    {
        for (int y = 0; y < height; ++y)
        {
            for (int x = 0; x < width; ++x)
            {
                Vec2 p(x, y);
                fn(p, at(p));
            }
        }
    }

    void forEach(function<void(const Vec2 &, const Cell &)> fn) const
    {
        for (int y = 0; y < height; ++y)
        {
            for (int x = 0; x < width; ++x)
            {
                Vec2 p(x, y);
                fn(p, at(p));
            }
        }
    }
};

struct EntityId
{
    int value;
    EntityId(int v = 0) : value(v) {}
    bool operator==(const EntityId &o) const { return value == o.value; }
    bool operator!=(const EntityId &o) const { return value != o.value; }
    bool operator<(const EntityId &o) const { return value < o.value; }
};

class World;

class Entity
{
protected:
    EntityId id;
    Vec2 position;
    bool alive;

public:
    Entity(EntityId id_, const Vec2 &pos)
        : id(id_), position(pos), alive(true)
    {
    }

    virtual ~Entity() {}

    EntityId getId() const
    {
        return id;
    }

    const Vec2 &getPos() const
    {
        return position;
    }

    void setPos(const Vec2 &p)
    {
        position = p;
    }

    bool isAlive() const
    {
        return alive;
    }

    void kill()
    {
        alive = false;
    }

    virtual void update(World &world, double dt) = 0;
    virtual char glyph() const = 0;
};

enum class EventType
{
    None,
    Arrive,
    Leave,
    Ping,
    Custom
};

struct Event
{
    EventType type;
    EntityId from;
    EntityId to;
    string payload;
    Vec2 pos;

    Event()
        : type(EventType::None), from(0), to(0), payload(""), pos(0, 0)
    {
    }

    Event(EventType t, EntityId f, EntityId tt, const string &pl, const Vec2 &p)
        : type(t), from(f), to(tt), payload(pl), pos(p)
    {
    }
};

class EventQueue
{
    vector<Event> events;
    vector<Event> nextEvents;

public:
    void push(const Event &e)
    {
        nextEvents.push_back(e);
    }

    void flip()
    {
        events.clear();
        events.swap(nextEvents);
    }

    const vector<Event> &getEvents() const
    {
        return events;
    }

    void clear()
    {
        events.clear();
        nextEvents.clear();
    }
};

struct PathNode
{
    Vec2 pos;
    double g;
    double h;
    double f;
    int parentIndex;
};

struct Pathfinding
{
    static bool neighbors(const Grid &grid, const Vec2 &p, vector<Vec2> &out)
    {
        static const Vec2 dirs[4] = {
            Vec2(1, 0),
            Vec2(-1, 0),
            Vec2(0, 1),
            Vec2(0, -1)};
        out.clear();
        for (int i = 0; i < 4; ++i)
        {
            Vec2 q = p + dirs[i];
            if (grid.inBounds(q))
            {
                const Cell &c = grid.at(q);
                if (c.type != CellType::Wall)
                {
                    out.push_back(q);
                }
            }
        }
        return !out.empty();
    }

    static double heuristic(const Vec2 &a, const Vec2 &b)
    {
        return std::abs(a.x - b.x) + std::abs(a.y - b.y);
    }

    static bool aStar(const Grid &grid, const Vec2 &start, const Vec2 &goal, vector<Vec2> &outPath)
    {
        outPath.clear();
        if (!grid.inBounds(start) || !grid.inBounds(goal))
        {
            return false;
        }

        vector<PathNode> nodes;
        nodes.reserve(1024);

        auto cmp = [&](int lhs, int rhs)
        {
            return nodes[lhs].f > nodes[rhs].f;
        };

        vector<int> open;
        vector<vector<int>> indexMap(grid.getHeight(), vector<int>(grid.getWidth(), -1));
        vector<bool> closed;

        nodes.push_back(PathNode{start, 0.0, heuristic(start, goal), heuristic(start, goal), -1});
        open.push_back(0);
        push_heap(open.begin(), open.end(), cmp);
        indexMap[start.y][start.x] = 0;
        closed.assign(1, false);

        vector<Vec2> neigh;

        while (!open.empty())
        {
            pop_heap(open.begin(), open.end(), cmp);
            int currentIndex = open.back();
            open.pop_back();

            if (closed[currentIndex])
            {
                continue;
            }

            PathNode &current = nodes[currentIndex];
            closed[currentIndex] = true;

            if (current.pos == goal)
            {
                int idx = currentIndex;
                while (idx != -1)
                {
                    outPath.push_back(nodes[idx].pos);
                    idx = nodes[idx].parentIndex;
                }
                reverse(outPath.begin(), outPath.end());
                return true;
            }

            neighbors(grid, current.pos, neigh);
            for (const Vec2 &nPos : neigh)
            {
                double tentativeG = current.g + 1.0;
                int &mapIndex = indexMap[nPos.y][nPos.x];

                if (mapIndex == -1)
                {
                    PathNode node;
                    node.pos = nPos;
                    node.g = tentativeG;
                    node.h = heuristic(nPos, goal);
                    node.f = node.g + node.h;
                    node.parentIndex = currentIndex;

                    int newIndex = static_cast<int>(nodes.size());
                    nodes.push_back(node);
                    closed.push_back(false);
                    mapIndex = newIndex;
                    open.push_back(newIndex);
                    push_heap(open.begin(), open.end(), cmp);
                }
                else
                {
                    PathNode &existing = nodes[mapIndex];
                    if (!closed[mapIndex] && tentativeG < existing.g)
                    {
                        existing.g = tentativeG;
                        existing.f = existing.g + existing.h;
                        existing.parentIndex = currentIndex;
                        open.push_back(mapIndex);
                        push_heap(open.begin(), open.end(), cmp);
                    }
                }
            }
        }

        return false;
    }
};

struct LSystemRule
{
    char from;
    string to;
};

class LSystem
{
    string axiom;
    vector<LSystemRule> rules;

public:
    void setAxiom(const string &a)
    {
        axiom = a;
    }

    void addRule(char f, const string &t)
    {
        rules.push_back(LSystemRule{f, t});
    }

    string generate(int iterations) const
    {
        string current = axiom;
        for (int i = 0; i < iterations; ++i)
        {
            string next;
            next.reserve(current.size() * 2);
            for (char c : current)
            {
                bool replaced = false;
                for (const auto &r : rules)
                {
                    if (r.from == c)
                    {
                        next += r.to;
                        replaced = true;
                        break;
                    }
                }
                if (!replaced)
                {
                    next.push_back(c);
                }
            }
            current.swap(next);
        }
        return current;
    }
};

class NoiseField
{
    int width;
    int height;
    vector<double> values;

public:
    NoiseField(int w = 0, int h = 0)
        : width(w), height(h), values(static_cast<size_t>(w * h), 0.0)
    {
    }

    void resize(int w, int h)
    {
        width = w;
        height = h;
        values.assign(static_cast<size_t>(w * h), 0.0);
    }

    double &at(int x, int y)
    {
        return values[static_cast<size_t>(y * width + x)];
    }

    const double &at(int x, int y) const
    {
        return values[static_cast<size_t>(y * width + x)];
    }

    int getWidth() const
    {
        return width;
    }

    int getHeight() const
    {
        return height;
    }

    void generate(RNG &rng, int octaves, double persistence)
    {
        if (width <= 0 || height <= 0)
        {
            return;
        }

        vector<double> base(values.size());
        for (auto &v : base)
        {
            v = rng.real01();
        }

        for (int y = 0; y < height; ++y)
        {
            for (int x = 0; x < width; ++x)
            {
                at(x, y) = 0.0;
            }
        }

        double amplitude = 1.0;
        double totalAmplitude = 0.0;

        for (int octave = 0; octave < octaves; ++octave)
        {
            int step = max(1, (1 << octave));
            for (int y = 0; y < height; ++y)
            {
                int y0 = (y / step) * step;
                int y1 = min(y0 + step, height - 1);
                double fy = (step == 0) ? 0.0 : (double)(y - y0) / (double)max(step, 1);

                for (int x = 0; x < width; ++x)
                {
                    int x0 = (x / step) * step;
                    int x1 = min(x0 + step, width - 1);
                    double fx = (step == 0) ? 0.0 : (double)(x - x0) / (double)max(step, 1);

                    double v00 = base[static_cast<size_t>(y0 * width + x0)];
                    double v10 = base[static_cast<size_t>(y0 * width + x1)];
                    double v01 = base[static_cast<size_t>(y1 * width + x0)];
                    double v11 = base[static_cast<size_t>(y1 * width + x1)];

                    double v0 = v00 + (v10 - v00) * fx;
                    double v1 = v01 + (v11 - v01) * fx;
                    double v = v0 + (v1 - v0) * fy;

                    at(x, y) += v * amplitude;
                }
            }

            totalAmplitude += amplitude;
            amplitude *= persistence;
        }

        if (totalAmplitude > 0.0)
        {
            for (auto &v : values)
            {
                v /= totalAmplitude;
            }
        }
    }
};

class World;

class Agent : public Entity
{
protected:
    Vec2 velocity;
    double speed;
    double phase;
    RNG localRng;

public:
    Agent(EntityId id_, const Vec2 &pos)
        : Entity(id_, pos), velocity(0, 0), speed(1.0), phase(0.0)
    {
    }

    void setSpeed(double s)
    {
        speed = s;
    }

    virtual void onEvent(World &world, const Event &e) = 0;

    void stepPosition(World &world, double dt);

    virtual ~Agent() {}
};

class Wanderer : public Agent
{
public:
    Wanderer(EntityId id_, const Vec2 &pos)
        : Agent(id_, pos)
    {
        speed = 1.0;
        phase = localRng.realRange(0.0, 1000.0);
    }

    void update(World &world, double dt) override;

    char glyph() const override
    {
        return 'w';
    }

    void onEvent(World &world, const Event &e) override;
};

class Seeker : public Agent
{
    Vec2 target;
    bool hasTarget;

public:
    Seeker(EntityId id_, const Vec2 &pos)
        : Agent(id_, pos), target(0, 0), hasTarget(false)
    {
        speed = 2.0;
    }

    void setTarget(const Vec2 &t)
    {
        target = t;
        hasTarget = true;
    }

    void update(World &world, double dt) override;

    char glyph() const override
    {
        return 's';
    }

    void onEvent(World &world, const Event &e) override;
};

class TrailMaker : public Agent
{
public:
    TrailMaker(EntityId id_, const Vec2 &pos)
        : Agent(id_, pos)
    {
        speed = 1.5;
    }

    void update(World &world, double dt) override;

    char glyph() const override
    {
        return 't';
    }

    void onEvent(World &world, const Event &e) override;
};

class SignalSource : public Agent
{
    double cooldown;
    double timer;

public:
    SignalSource(EntityId id_, const Vec2 &pos)
        : Agent(id_, pos), cooldown(1.0), timer(0.0)
    {
        speed = 0.0;
    }

    void update(World &world, double dt) override;

    char glyph() const override
    {
        return 'o';
    }

    void onEvent(World &world, const Event &e) override;
};

class SignalSink : public Agent
{
public:
    SignalSink(EntityId id_, const Vec2 &pos)
        : Agent(id_, pos)
    {
        speed = 0.0;
    }

    void update(World &world, double dt) override;

    char glyph() const override
    {
        return 'x';
    }

    void onEvent(World &world, const Event &e) override;
};

class Recorder
{
    vector<string> lines;
    bool enabled;
    size_t maxLines;

public:
    Recorder()
        : enabled(false), maxLines(2000)
    {
    }

    void setEnabled(bool e)
    {
        enabled = e;
    }

    bool isEnabled() const
    {
        return enabled;
    }

    void setMaxLines(size_t m)
    {
        maxLines = m;
    }

    void log(const string &s)
    {
        if (!enabled)
        {
            return;
        }
        if (lines.size() >= maxLines)
        {
            lines.erase(lines.begin());
        }
        lines.push_back(s);
    }

    void saveToFile(const string &filename) const
    {
        ofstream out(filename);
        for (const auto &line : lines)
        {
            out << line << "\n";
        }
    }
};

struct Command
{
    string name;
    vector<string> args;
};

class CommandParser
{
public:
    static Command parse(const string &line)
    {
        Command cmd;
        string token;
        istringstream iss(line);
        if (!(iss >> cmd.name))
        {
            cmd.name.clear();
            return cmd;
        }
        while (iss >> token)
        {
            cmd.args.push_back(token);
        }
        return cmd;
    }
};

struct WorldConfig
{
    int width;
    int height;
    int wanderers;
    int seekers;
    int trails;
    int sources;
    int sinks;
    unsigned seed;
};

class World
{
    Grid grid;
    NoiseField noise;
    RNG rng;
    vector<unique_ptr<Entity>> entities;
    EventQueue events;
    Recorder recorder;
    int nextId;
    int tick;
    WorldConfig config;
    vector<Vec2> cachedSources;
    vector<Vec2> cachedSinks;
    vector<Vec2> cachedEmptyCells;
    bool running;
    bool redrawRequired;
    double timeAccum;
    double timestep;
    bool showOverlay;
    bool showNoise;
    bool showIds;
    bool advancedMode;
    vector<Vec2> debugPath;

public:
    World()
        : grid(0, 0),
          noise(0, 0),
          rng(),
          nextId(1),
          tick(0),
          running(true),
          redrawRequired(true),
          timeAccum(0.0),
          timestep(0.1),
          showOverlay(true),
          showNoise(false),
          showIds(false),
          advancedMode(true)
    {
        config.width = 60;
        config.height = 24;
        config.wanderers = 12;
        config.seekers = 4;
        config.trails = 6;
        config.sources = 4;
        config.sinks = 4;
        config.seed = static_cast<unsigned>(chrono::high_resolution_clock::now().time_since_epoch().count());
    }

    void init()
    {
        rng.seed(config.seed);
        grid.resize(config.width, config.height);
        noise.resize(config.width, config.height);
        grid.fill(CellType::Empty);
        noise.generate(rng, 5, 0.5);
        generateLayout();
        spawnEntities();
        rebuildCaches();
    }

    void generateLayout()
    {
        for (int y = 0; y < grid.getHeight(); ++y)
        {
            for (int x = 0; x < grid.getWidth(); ++x)
            {
                Vec2 p(x, y);
                Cell &c = grid.at(p);
                if (y == 0 || y == grid.getHeight() - 1 || x == 0 || x == grid.getWidth() - 1)
                {
                    c.type = CellType::Wall;
                }
                else
                {
                    double v = noise.at(x, y);
                    if (v < 0.12)
                    {
                        c.type = CellType::Wall;
                    }
                    else if (v > 0.88)
                    {
                        c.type = CellType::MarkerC;
                    }
                    else if (v > 0.72)
                    {
                        c.type = CellType::MarkerB;
                    }
                    else if (v > 0.55)
                    {
                        c.type = CellType::MarkerA;
                    }
                    else
                    {
                        c.type = CellType::Empty;
                    }
                }
                c.value1 = noise.at(x, y);
                c.value2 = 0.0;
            }
        }
    }

    void spawnEntities()
    {
        for (int i = 0; i < config.wanderers; ++i)
        {
            Vec2 p = randomEmptyCell();
            addEntity(make_unique<Wanderer>(allocId(), p));
        }
        for (int i = 0; i < config.seekers; ++i)
        {
            Vec2 p = randomEmptyCell();
            addEntity(make_unique<Seeker>(allocId(), p));
        }
        for (int i = 0; i < config.trails; ++i)
        {
            Vec2 p = randomEmptyCell();
            addEntity(make_unique<TrailMaker>(allocId(), p));
        }
        for (int i = 0; i < config.sources; ++i)
        {
            Vec2 p = randomEmptyCell();
            addEntity(make_unique<SignalSource>(allocId(), p));
            grid.at(p).type = CellType::Source;
        }
        for (int i = 0; i < config.sinks; ++i)
        {
            Vec2 p = randomEmptyCell();
            addEntity(make_unique<SignalSink>(allocId(), p));
            grid.at(p).type = CellType::Sink;
        }
    }

    void rebuildCaches()
    {
        cachedSources.clear();
        cachedSinks.clear();
        cachedEmptyCells.clear();
        for (int y = 0; y < grid.getHeight(); ++y)
        {
            for (int x = 0; x < grid.getWidth(); ++x)
            {
                Vec2 p(x, y);
                const Cell &c = grid.at(p);
                if (c.type == CellType::Source)
                {
                    cachedSources.push_back(p);
                }
                else if (c.type == CellType::Sink)
                {
                    cachedSinks.push_back(p);
                }
                else if (c.type == CellType::Empty || c.type == CellType::Trail || c.type == CellType::MarkerA || c.type == CellType::MarkerB || c.type == CellType::MarkerC)
                {
                    cachedEmptyCells.push_back(p);
                }
            }
        }
    }

    Vec2 randomEmptyCell()
    {
        if (cachedEmptyCells.empty())
        {
            rebuildCaches();
        }
        if (cachedEmptyCells.empty())
        {
            return Vec2(1, 1);
        }
        return rng.choice(cachedEmptyCells);
    }

    EntityId allocId()
    {
        return EntityId(nextId++);
    }

    void addEntity(unique_ptr<Entity> e)
    {
        entities.push_back(move(e));
    }

    RNG &random()
    {
        return rng;
    }

    Grid &getGrid()
    {
        return grid;
    }

    const Grid &getGrid() const
    {
        return grid;
    }

    EventQueue &getEvents()
    {
        return events;
    }

    const EventQueue &getEvents() const
    {
        return events;
    }

    Recorder &getRecorder()
    {
        return recorder;
    }

    bool isRunning() const
    {
        return running;
    }

    void requestRedraw()
    {
        redrawRequired = true;
    }

    void broadcast(const Event &e)
    {
        events.push(e);
    }

    void step(double dt)
    {
        if (!running)
        {
            return;
        }

        timeAccum += dt;
        while (timeAccum >= timestep)
        {
            tick++;
            timeAccum -= timestep;
            events.flip();

            for (const Event &e : events.getEvents())
            {
                for (auto &ptr : entities)
                {
                    if (ptr && ptr->isAlive())
                    {
                        Agent *agent = dynamic_cast<Agent *>(ptr.get());
                        if (agent)
                        {
                            agent->onEvent(*this, e);
                        }
                    }
                }
            }

            for (auto &ptr : entities)
            {
                if (ptr && ptr->isAlive())
                {
                    ptr->update(*this, timestep);
                }
            }

            entities.erase(
                remove_if(entities.begin(), entities.end(),
                          [](const unique_ptr<Entity> &p)
                          {
                              return !p || !p->isAlive();
                          }),
                entities.end());

            evaporateTrails();
            redrawRequired = true;
        }
    }

    void evaporateTrails()
    {
        grid.forEach([&](const Vec2 &p, Cell &c)
                     {
                         if (c.type == CellType::Trail || c.type == CellType::Signal)
                         {
                             c.value2 += 0.02;
                             if (c.value2 >= 1.0)
                             {
                                 c.type = CellType::Empty;
                                 c.value2 = 0.0;
                             }
                         }
                     });
    }

    void render(ostream &os)
    {
        if (!redrawRequired)
        {
            return;
        }

        vector<string> lines;
        lines.resize(static_cast<size_t>(grid.getHeight()));
        for (int y = 0; y < grid.getHeight(); ++y)
        {
            lines[static_cast<size_t>(y)].assign(static_cast<size_t>(grid.getWidth()), ' ');
        }

        grid.forEach([&](const Vec2 &p, const Cell &c)
                     {
                         char ch = ' ';
                         if (showNoise)
                         {
                             double v = c.value1;
                             if (v < 0.2)
                                 ch = ' ';
                             else if (v < 0.4)
                                 ch = '.';
                             else if (v < 0.6)
                                 ch = '-';
                             else if (v < 0.8)
                                 ch = '+';
                             else
                                 ch = '#';
                         }
                         else
                         {
                             ch = cellTypeToChar(c.type);
                         }

                         lines[static_cast<size_t>(p.y)][static_cast<size_t>(p.x)] = ch;
                     });

        for (const auto &nodePos : debugPath)
        {
            if (grid.inBounds(nodePos))
            {
                lines[static_cast<size_t>(nodePos.y)][static_cast<size_t>(nodePos.x)] = '@';
            }
        }

        for (const auto &ptr : entities)
        {
            if (ptr && ptr->isAlive())
            {
                Vec2 p = ptr->getPos();
                if (grid.inBounds(p))
                {
                    lines[static_cast<size_t>(p.y)][static_cast<size_t>(p.x)] = ptr->glyph();
                }
            }
        }

        os << "\x1b[H";
        for (int y = 0; y < grid.getHeight(); ++y)
        {
            os << lines[static_cast<size_t>(y)] << "\n";
        }

        if (showOverlay)
        {
            os << "\n";
            os << "tick: " << tick
               << " entities: " << entities.size()
               << " running: " << (running ? "yes" : "no")
               << " mode: " << (advancedMode ? "advanced" : "basic")
               << " overlay: " << (showOverlay ? "on" : "off")
               << " noise: " << (showNoise ? "on" : "off")
               << " ids: " << (showIds ? "on" : "off")
               << "\n";
            os << "commands: "
               << "[p]ause/[r]esume, [q]uit, [n]oise, [o]verlay, [c]lear path, "
               << "[a]dv mode, [s]ave log <file>, [g]enerate path, [?]help\n";
        }

        redrawRequired = false;
    }

    void handleCommand(const Command &cmd)
    {
        if (cmd.name.empty())
        {
            return;
        }

        if (cmd.name == "q" || cmd.name == "quit" || cmd.name == "exit")
        {
            running = false;
        }
        else if (cmd.name == "p" || cmd.name == "pause")
        {
            running = false;
        }
        else if (cmd.name == "r" || cmd.name == "resume")
        {
            running = true;
        }
        else if (cmd.name == "overlay" || cmd.name == "o")
        {
            showOverlay = !showOverlay;
            requestRedraw();
        }
        else if (cmd.name == "noise" || cmd.name == "n")
        {
            showNoise = !showNoise;
            requestRedraw();
        }
        else if (cmd.name == "ids" || cmd.name == "i")
        {
            showIds = !showIds;
            requestRedraw();
        }
        else if (cmd.name == "rec" || cmd.name == "record")
        {
            recorder.setEnabled(!recorder.isEnabled());
        }
        else if (cmd.name == "save" || cmd.name == "s")
        {
            if (!cmd.args.empty())
            {
                recorder.saveToFile(cmd.args[0]);
            }
        }
        else if (cmd.name == "regen")
        {
            debugPath.clear();
            entities.clear();
            grid.fill(CellType::Empty);
            noise.generate(rng, 5, 0.5);
            generateLayout();
            spawnEntities();
            rebuildCaches();
            requestRedraw();
        }
        else if (cmd.name == "step")
        {
            if (!cmd.args.empty())
            {
                int n = stoi(cmd.args[0]);
                for (int i = 0; i < n; ++i)
                {
                    step(timestep);
                }
            }
            else
            {
                step(timestep);
            }
        }
        else if (cmd.name == "help" || cmd.name == "?")
        {
            cout << "basic commands:\n";
            cout << "  q/quit/exit     - stop\n";
            cout << "  p/pause         - pause\n";
            cout << "  r/resume        - resume\n";
            cout << "  overlay/o       - toggle overlay\n";
            cout << "  noise/n         - toggle noise mode\n";
            cout << "  ids/i           - toggle ids\n";
            cout << "  regen           - regenerate world\n";
            cout << "  step [n]        - step n ticks (default 1)\n";
            cout << "  rec/record      - toggle recording\n";
            cout << "  save/s <file>   - save recording\n";
            cout << "  g/genpath       - generate a path between source and sink\n";
            cout << "  c/clear         - clear path\n";
        }
        else if (cmd.name == "genpath" || cmd.name == "g")
        {
            generatePathBetweenSourceAndSink();
        }
        else if (cmd.name == "clear" || cmd.name == "c")
        {
            debugPath.clear();
            requestRedraw();
        }
        else if (cmd.name == "mode" || cmd.name == "a")
        {
            advancedMode = !advancedMode;
            requestRedraw();
        }
    }

    void generatePathBetweenSourceAndSink()
    {
        if (cachedSources.empty() || cachedSinks.empty())
        {
            rebuildCaches();
        }

        if (cachedSources.empty() || cachedSinks.empty())
        {
            return;
        }

        Vec2 s = rng.choice(cachedSources);
        Vec2 t = rng.choice(cachedSinks);

        vector<Vec2> path;
        bool ok = Pathfinding::aStar(grid, s, t, path);
        if (ok)
        {
            debugPath = path;
            requestRedraw();
        }
    }

    void addTrailAt(const Vec2 &p)
    {
        if (grid.inBounds(p))
        {
            Cell &c = grid.at(p);
            if (c.type == CellType::Empty || c.type == CellType::MarkerA || c.type == CellType::MarkerB || c.type == CellType::MarkerC)
            {
                c.type = CellType::Trail;
                c.value2 = 0.0;
            }
        }
    }

    void addSignalAt(const Vec2 &p)
    {
        if (grid.inBounds(p))
        {
            Cell &c = grid.at(p);
            if (c.type == CellType::Empty || c.type == CellType::Trail)
            {
                c.type = CellType::Signal;
                c.value2 = 0.0;
            }
        }
    }

    Vec2 randomSource() const
    {
        if (cachedSources.empty())
        {
            return Vec2(1, 1);
        }
        return rng.choice(cachedSources);
    }

    Vec2 randomSink() const
    {
        if (cachedSinks.empty())
        {
            return Vec2(1, 1);
        }
        return rng.choice(cachedSinks);
    }

    int getTick() const
    {
        return tick;
    }

    bool isAdvancedMode() const
    {
        return advancedMode;
    }

    bool isShowIds() const
    {
        return showIds;
    }
};

void Agent::stepPosition(World &world, double dt)
{
    Vec2 pos = getPos();
    Vec2 targetPos = pos;

    double dx = velocity.x * dt * speed;
    double dy = velocity.y * dt * speed;

    double accx = 0.0;
    double accy = 0.0;

    if (dx > 0.5)
        accx = 1.0;
    else if (dx < -0.5)
        accx = -1.0;

    if (dy > 0.5)
        accy = 1.0;
    else if (dy < -0.5)
        accy = -1.0;

    if (std::abs(dx) >= 1.0 || std::abs(dy) >= 1.0)
    {
        int stepCount = static_cast<int>(max(std::abs(dx), std::abs(dy)));
        double stepX = dx / stepCount;
        double stepY = dy / stepCount;
        double fx = pos.x;
        double fy = pos.y;
        for (int i = 0; i < stepCount; ++i)
        {
            fx += stepX;
            fy += stepY;
            Vec2 candidate(static_cast<int>(std::round(fx)), static_cast<int>(std::round(fy)));
            if (candidate != pos && world.getGrid().inBounds(candidate))
            {
                const Cell &c = world.getGrid().at(candidate);
                if (c.type != CellType::Wall)
                {
                    pos = candidate;
                }
            }
        }
    }
    else
    {
        int mx = 0;
        int my = 0;
        if (std::abs(dx) >= 0.5)
            mx = (dx > 0 ? 1 : -1);
        if (std::abs(dy) >= 0.5)
            my = (dy > 0 ? 1 : -1);
        Vec2 candidate = pos + Vec2(mx, my);
        if (world.getGrid().inBounds(candidate))
        {
            const Cell &c = world.getGrid().at(candidate);
            if (c.type != CellType::Wall)
            {
                pos = candidate;
            }
        }
    }

    setPos(pos);
    world.addTrailAt(pos);
}

void Wanderer::update(World &world, double dt)
{
    phase += dt;
    if (localRng.chance(0.15))
    {
        int dir = localRng.intInRange(0, 3);
        if (dir == 0)
            velocity = Vec2(1, 0);
        else if (dir == 1)
            velocity = Vec2(-1, 0);
        else if (dir == 2)
            velocity = Vec2(0, 1);
        else
            velocity = Vec2(0, -1);
    }
    stepPosition(world, dt);
}

void Wanderer::onEvent(World &world, const Event &e)
{
    (void)world;
    (void)e;
}

void Seeker::update(World &world, double dt)
{
    if (!hasTarget)
    {
        target = world.randomSink();
        hasTarget = true;
    }

    Vec2 pos = getPos();
    Vec2 diff(target.x - pos.x, target.y - pos.y);

    if (diff.x == 0 && diff.y == 0)
    {
        hasTarget = false;
        world.broadcast(Event(EventType::Arrive, getId(), EntityId(0), "", pos));
    }
    else
    {
        int bestDx = 0;
        int bestDy = 0;
        if (std::abs(diff.x) > std::abs(diff.y))
        {
            if (diff.x > 0)
                bestDx = 1;
            else if (diff.x < 0)
                bestDx = -1;
        }
        else
        {
            if (diff.y > 0)
                bestDy = 1;
            else if (diff.y < 0)
                bestDy = -1;
        }
        velocity = Vec2(bestDx, bestDy);
        stepPosition(world, dt);
    }
}

void Seeker::onEvent(World &world, const Event &e)
{
    (void)world;
    if (e.type == EventType::Ping)
    {
        if (world.random().chance(0.2))
        {
            target = e.pos;
            hasTarget = true;
        }
    }
}

void TrailMaker::update(World &world, double dt)
{
    if (world.isAdvancedMode())
    {
        const Grid &grid = world.getGrid();
        Vec2 pos = getPos();
        double bestScore = -std::numeric_limits<double>::infinity();
        Vec2 bestDir(0, 0);

        static const Vec2 dirs[4] = {
            Vec2(1, 0),
            Vec2(-1, 0),
            Vec2(0, 1),
            Vec2(0, -1)};

        for (const Vec2 &d : dirs)
        {
            Vec2 q = pos + d;
            if (grid.inBounds(q))
            {
                const Cell &c = grid.at(q);
                double score = 0.0;
                if (c.type == CellType::MarkerA)
                    score += 0.5;
                if (c.type == CellType::MarkerB)
                    score += 1.0;
                if (c.type == CellType::MarkerC)
                    score += 1.5;
                if (c.type == CellType::Trail)
                    score -= 0.2;
                if (c.type == CellType::Signal)
                    score += 0.3;
                score += c.value1 * 0.1;
                score += world.random().realRange(-0.05, 0.05);

                if (score > bestScore)
                {
                    bestScore = score;
                    bestDir = d;
                }
            }
        }

        velocity = bestDir;
    }
    else
    {
        if (world.random().chance(0.4))
        {
            int dir = world.random().intInRange(0, 3);
            if (dir == 0)
                velocity = Vec2(1, 0);
            else if (dir == 1)
                velocity = Vec2(-1, 0);
            else if (dir == 2)
                velocity = Vec2(0, 1);
            else
                velocity = Vec2(0, -1);
        }
    }

    stepPosition(world, dt);
}

void TrailMaker::onEvent(World &world, const Event &e)
{
    (void)world;
    (void)e;
}

void SignalSource::update(World &world, double dt)
{
    timer += dt;
    if (timer >= cooldown)
    {
        timer -= cooldown;
        Vec2 pos = getPos();
        world.addSignalAt(pos);
        world.broadcast(Event(EventType::Ping, getId(), EntityId(0), "signal", pos));
    }
}

void SignalSource::onEvent(World &world, const Event &e)
{
    (void)world;
    (void)e;
}

void SignalSink::update(World &world, double dt)
{
    (void)world;
    (void)dt;
}

void SignalSink::onEvent(World &world, const Event &e)
{
    if (e.type == EventType::Arrive)
    {
        (void)e;
    }
}

int main()
{
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    World world;
    world.init();

    cout << "\x1b[2J";
    world.requestRedraw();
    world.render(cout);

    auto last = chrono::high_resolution_clock::now();

    string line;
    bool interactive = true;

    while (true)
    {
        auto now = chrono::high_resolution_clock::now();
        double dt = chrono::duration<double>(now - last).count();
        last = now;

        world.step(dt);
        world.render(cout);

        if (!world.isRunning())
        {
            cout << "\npaused. enter command (or 'q' to quit): ";
        }

        if (interactive)
        {
            if (!getline(cin, line))
            {
                break;
            }
            Command cmd = CommandParser::parse(line);
            if (!cmd.name.empty())
            {
                world.handleCommand(cmd);
                if (!world.isRunning())
                {
                    world.render(cout);
                }
                if (cmd.name == "q" || cmd.name == "quit" || cmd.name == "exit")
                {
                    break;
                }
            }
        }
        else
        {
            if (!world.isRunning())
            {
                break;
            }
        }
    }

    return 0;
}
