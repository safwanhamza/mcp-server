;(function ()
{
    const TAU = Math.PI * 2
    const rand = (min, max) => Math.random() * (max - min) + min
    const randInt = (min, max) => Math.floor(rand(min, max + 1))
    const clamp = (v, min, max) => v < min ? min : v > max ? max : v
    const lerp = (a, b, t) => a + (b - a) * t
    const easeInOutQuad = t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t
    const smoothstep = (edge0, edge1, x) =>
    {
        const t = clamp((x - edge0) / (edge1 - edge0), 0, 1)
        return t * t * (3 - 2 * t)
    }
    const map = (v, inMin, inMax, outMin, outMax) =>
    {
        return outMin + (outMax - outMin) * ((v - inMin) / (inMax - inMin))
    }

    const createCanvas = () =>
    {
        const c = document.createElement('canvas')
        document.body.style.margin = '0'
        document.body.style.overflow = 'hidden'
        document.body.appendChild(c)
        return c
    }

    const canvas = createCanvas()
    const ctx = canvas.getContext('2d')

    let width = window.innerWidth
    let height = window.innerHeight

    const resize = () =>
    {
        width = window.innerWidth
        height = window.innerHeight
        canvas.width = width * window.devicePixelRatio
        canvas.height = height * window.devicePixelRatio
        ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0)
    }

    resize()
    window.addEventListener('resize', resize)

    let mouseX = width / 2
    let mouseY = height / 2
    let pmouseX = mouseX
    let pmouseY = mouseY
    let mouseDown = false

    window.addEventListener('mousemove', e =>
    {
        pmouseX = mouseX
        pmouseY = mouseY
        mouseX = e.clientX
        mouseY = e.clientY
    })

    window.addEventListener('mousedown', e =>
    {
        mouseDown = true
    })

    window.addEventListener('mouseup', e =>
    {
        mouseDown = false
    })

    window.addEventListener('touchstart', e =>
    {
        mouseDown = true
        const t = e.touches[0]
        mouseX = t.clientX
        mouseY = t.clientY
    })

    window.addEventListener('touchmove', e =>
    {
        const t = e.touches[0]
        pmouseX = mouseX
        pmouseY = mouseY
        mouseX = t.clientX
        mouseY = t.clientY
    })

    window.addEventListener('touchend', e =>
    {
        mouseDown = false
    })

    const createVector = (x = 0, y = 0) =>
    {
        return { x, y }
    }

    const addVec = (a, b) =>
    {
        a.x += b.x
        a.y += b.y
    }

    const subVec = (a, b) =>
    {
        a.x -= b.x
        a.y -= b.y
    }

    const mulVec = (a, s) =>
    {
        a.x *= s
        a.y *= s
    }

    const lengthVec = v =>
    {
        return Math.sqrt(v.x * v.x + v.y * v.y)
    }

    const normalizeVec = v =>
    {
        const l = lengthVec(v)
        if (l > 0)
        {
            v.x /= l
            v.y /= l
        }
    }

    const setMagVec = (v, m) =>
    {
        normalizeVec(v)
        mulVec(v, m)
    }

    const copyVec = v =>
    {
        return { x: v.x, y: v.y }
    }

    const distVec = (a, b) =>
    {
        const dx = a.x - b.x
        const dy = a.y - b.y
        return Math.sqrt(dx * dx + dy * dy)
    }

    const rotateVec = (v, angle) =>
    {
        const c = Math.cos(angle)
        const s = Math.sin(angle)
        const x = v.x * c - v.y * s
        const y = v.x * s + v.y * c
        v.x = x
        v.y = y
    }

    class FlowField
    {
        constructor(cols, rows, scale)
        {
            this.cols = cols
            this.rows = rows
            this.scale = scale
            this.field = new Array(cols * rows).fill(0).map(() => createVector())
            this.time = 0
        }
        index(x, y)
        {
            return x + y * this.cols
        }
        sample(x, y)
        {
            const gx = Math.floor(clamp(x / this.scale, 0, this.cols - 1))
            const gy = Math.floor(clamp(y / this.scale, 0, this.rows - 1))
            return this.field[this.index(gx, gy)]
        }
        update(dt)
        {
            this.time += dt * 0.0001
            for (let y = 0; y < this.rows; y++)
            {
                for (let x = 0; x < this.cols; x++)
                {
                    const i = this.index(x, y)
                    const nx = x / this.cols
                    const ny = y / this.rows
                    const a = Math.sin((nx + this.time) * Math.PI * 4) + Math.cos((ny - this.time) * Math.PI * 3)
                    const b = Math.cos((ny + this.time) * Math.PI * 2) - Math.sin((nx - this.time) * Math.PI * 5)
                    const ang = Math.atan2(b, a)
                    this.field[i].x = Math.cos(ang)
                    this.field[i].y = Math.sin(ang)
                }
            }
        }
    }

    class Particle
    {
        constructor(x, y)
        {
            this.pos = createVector(x, y)
            this.vel = createVector(rand(-1, 1), rand(-1, 1))
            this.acc = createVector(0, 0)
            this.maxSpeed = rand(0.5, 3)
            this.life = rand(0.4, 1)
            this.age = 0
            this.hue = rand(0, 360)
            this.size = rand(0.5, 3)
            this.noiseOffset = rand(0, 10000)
            this.trail = []
            this.trailMax = randInt(10, 50)
        }
        applyForce(f)
        {
            addVec(this.acc, f)
        }
        follow(flow)
        {
            const v = flow.sample(this.pos.x, this.pos.y)
            const force = copyVec(v)
            mulVec(force, 0.3)
            this.applyForce(force)
        }
        update(dt)
        {
            this.age += dt
            addVec(this.vel, this.acc)
            const len = lengthVec(this.vel)
            if (len > this.maxSpeed)
            {
                setMagVec(this.vel, this.maxSpeed)
            }
            addVec(this.pos, this.vel)
            this.trail.push(copyVec(this.pos))
            if (this.trail.length > this.trailMax)
            {
                this.trail.shift()
            }
            this.acc.x = 0
            this.acc.y = 0
            if (this.pos.x < 0) this.pos.x = width
            if (this.pos.x > width) this.pos.x = 0
            if (this.pos.y < 0) this.pos.y = height
            if (this.pos.y > height) this.pos.y = 0
        }
        drawTrail(ctx)
        {
            if (this.trail.length < 2) return
            ctx.beginPath()
            for (let i = 0; i < this.trail.length - 1; i++)
            {
                const p = this.trail[i]
                if (i === 0) ctx.moveTo(p.x, p.y)
                else ctx.lineTo(p.x, p.y)
            }
            const alpha = smoothstep(0, this.life, this.life - this.age)
            ctx.strokeStyle = `hsla(${this.hue},80%,60%,${alpha})`
            ctx.lineWidth = this.size
            ctx.stroke()
        }
        draw(ctx)
        {
            const alpha = smoothstep(0, this.life, this.life - this.age)
            ctx.fillStyle = `hsla(${this.hue},80%,60%,${alpha})`
            ctx.beginPath()
            ctx.arc(this.pos.x, this.pos.y, this.size * 1.5, 0, TAU)
            ctx.fill()
        }
        isDead()
        {
            return this.age > this.life
        }
    }

    class Attractor
    {
        constructor(x, y, strength)
        {
            this.pos = createVector(x, y)
            this.strength = strength
            this.radius = rand(40, 140)
            this.pulse = rand(0.4, 1)
            this.phase = rand(0, TAU)
            this.hue = rand(0, 360)
        }
        applyTo(p)
        {
            const dir = { x: this.pos.x - p.pos.x, y: this.pos.y - p.pos.y }
            const d = lengthVec(dir)
            if (d === 0) return
            const r = this.radius
            const f = smoothstep(r * 0.5, r, d)
            const inv = 1 - f
            normalizeVec(dir)
            mulVec(dir, this.strength * inv * 0.1)
            p.applyForce(dir)
        }
        draw(ctx, t)
        {
            const k = (Math.sin(t * this.pulse + this.phase) + 1) * 0.5
            const r = lerp(this.radius * 0.6, this.radius * 1.2, k)
            const alpha = 0.1 + 0.25 * k
            const widthMult = 1 + k * 3
            ctx.save()
            ctx.beginPath()
            ctx.arc(this.pos.x, this.pos.y, r, 0, TAU)
            ctx.strokeStyle = `hsla(${this.hue},80%,60%,${alpha})`
            ctx.lineWidth = widthMult
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(this.pos.x, this.pos.y, r * 0.2, 0, TAU)
            ctx.fillStyle = `hsla(${this.hue},80%,70%,${0.5 + 0.4 * k})`
            ctx.fill()
            ctx.restore()
        }
    }

    class Orb
    {
        constructor()
        {
            this.center = createVector(width / 2, height / 2)
            this.radius = Math.min(width, height) * 0.2
            this.angle = rand(0, TAU)
            this.speed = rand(0.0001, 0.0006)
            this.hue = rand(0, 360)
            this.size = rand(6, 16)
            this.spin = rand(-0.0003, 0.0003)
        }
        update(dt, t)
        {
            this.angle += this.speed * dt
            this.center.x = width / 2 + Math.cos(this.angle * 2) * this.radius * 0.5
            this.center.y = height / 2 + Math.sin(this.angle * 1.5) * this.radius * 0.5
            this.radius += Math.sin(t * 0.0002 + this.angle) * 0.02
        }
        posOnRing(i, n)
        {
            const aa = this.angle * (1 + this.spin * i)
            const ang = aa + (TAU * i) / n
            return {
                x: this.center.x + Math.cos(ang) * this.radius,
                y: this.center.y + Math.sin(ang) * this.radius
            }
        }
        draw(ctx, t)
        {
            const segments = 24
            for (let i = 0; i < segments; i++)
            {
                const p = this.posOnRing(i, segments)
                const k = i / segments
                const s = this.size * (0.4 + 0.6 * Math.sin(t * 0.001 + k * TAU) ** 2)
                ctx.beginPath()
                ctx.arc(p.x, p.y, s, 0, TAU)
                const alpha = 0.3 + 0.4 * Math.sin(t * 0.0012 + k * TAU) ** 2
                ctx.fillStyle = `hsla(${this.hue + k * 60},80%,60%,${alpha})`
                ctx.fill()
            }
        }
    }

    class PolygonNetwork
    {
        constructor(count)
        {
            this.points = []
            this.links = []
            this.hueOffset = rand(0, 360)
            for (let i = 0; i < count; i++)
            {
                const p = {
                    pos: createVector(rand(0, width), rand(0, height)),
                    vel: createVector(rand(-0.2, 0.2), rand(-0.2, 0.2)),
                    mass: rand(0.6, 1.4)
                }
                this.points.push(p)
            }
            for (let i = 0; i < count; i++)
            {
                for (let j = i + 1; j < count; j++)
                {
                    const p1 = this.points[i]
                    const p2 = this.points[j]
                    const d = distVec(p1.pos, p2.pos)
                    if (d < Math.min(width, height) * 0.3)
                    {
                        this.links.push({ a: i, b: j, baseDist: d })
                    }
                }
            }
        }
        update(dt, t)
        {
            const ms = dt * 0.06
            for (let p of this.points)
            {
                addVec(p.pos, { x: p.vel.x * ms, y: p.vel.y * ms })
                if (p.pos.x < 0 || p.pos.x > width) p.vel.x *= -1
                if (p.pos.y < 0 || p.pos.y > height) p.vel.y *= -1
            }
            const pullCenter = createVector(width / 2, height / 2)
            for (let p of this.points)
            {
                const dir = { x: pullCenter.x - p.pos.x, y: pullCenter.y - p.pos.y }
                const d = lengthVec(dir)
                if (d > 0)
                {
                    normalizeVec(dir)
                    const s = smoothstep(Math.min(width, height) * 0.1, Math.min(width, height) * 0.5, d)
                    mulVec(dir, s * 0.02 * p.mass * ms)
                    addVec(p.pos, dir)
                }
            }
        }
        draw(ctx, t)
        {
            const tt = t * 0.0002
            ctx.lineCap = 'round'
            for (let link of this.links)
            {
                const p1 = this.points[link.a]
                const p2 = this.points[link.b]
                const d = distVec(p1.pos, p2.pos)
                const f = clamp(d / (link.baseDist * 2), 0, 1)
                const strength = 1 - f
                if (strength <= 0.02) continue
                const mid = { x: (p1.pos.x + p2.pos.x) * 0.5, y: (p1.pos.y + p2.pos.y) * 0.5 }
                const angle = Math.atan2(p2.pos.y - p1.pos.y, p2.pos.x - p1.pos.x)
                const offset = Math.sin(tt + link.a * 0.1 + link.b * 0.07) * 10 * strength
                const cp = {
                    x: mid.x + Math.cos(angle + Math.PI / 2) * offset,
                    y: mid.y + Math.sin(angle + Math.PI / 2) * offset
                }
                ctx.beginPath()
                ctx.moveTo(p1.pos.x, p1.pos.y)
                ctx.quadraticCurveTo(cp.x, cp.y, p2.pos.x, p2.pos.y)
                const hue = this.hueOffset + strength * 180 + Math.sin(tt * 5 + link.a * 0.7) * 40
                const alpha = 0.2 + strength * 0.5
                ctx.strokeStyle = `hsla(${hue},80%,70%,${alpha})`
                ctx.lineWidth = 0.5 + strength * 3
                ctx.stroke()
            }
            for (let i = 0; i < this.points.length; i++)
            {
                const p = this.points[i]
                const radius = 2 + Math.sin(t * 0.002 + i * 0.3) * 2
                const distToMouse = distVec(p.pos, { x: mouseX, y: mouseY })
                const highlight = smoothstep(150, 0, distToMouse)
                ctx.beginPath()
                ctx.arc(p.pos.x, p.pos.y, radius + highlight * 4, 0, TAU)
                const hue = this.hueOffset + i * 3
                const alpha = 0.6 + highlight * 0.4
                ctx.fillStyle = `hsla(${hue},80%,65%,${alpha})`
                ctx.fill()
            }
        }
    }

    class Ribbon
    {
        constructor()
        {
            this.points = []
            this.maxPoints = 200
            this.hueBase = rand(0, 360)
            this.noise = rand(0, 10000)
        }
        push(x, y)
        {
            this.points.unshift({ x, y })
            if (this.points.length > this.maxPoints) this.points.pop()
        }
        update(dt, t)
        {
            const nx = mouseX + Math.sin(t * 0.001) * 30
            const ny = mouseY + Math.cos(t * 0.0013) * 30
            this.push(nx, ny)
        }
        draw(ctx, t)
        {
            if (this.points.length < 2) return
            ctx.beginPath()
            const len = this.points.length
            for (let i = 0; i < len - 1; i++)
            {
                const p = this.points[i]
                const next = this.points[i + 1]
                const k = i / len
                if (i === 0) ctx.moveTo(p.x, p.y)
                const mx = (p.x + next.x) * 0.5
                const my = (p.y + next.y) * 0.5
                ctx.quadraticCurveTo(p.x, p.y, mx, my)
            }
            const hue = this.hueBase + Math.sin(t * 0.0005) * 80
            ctx.strokeStyle = `hsla(${hue},90%,70%,0.7)`
            ctx.lineWidth = 4
            ctx.stroke()
            for (let i = 0; i < len; i += 10)
            {
                const p = this.points[i]
                const k = i / len
                const s = 2 + 4 * k
                ctx.beginPath()
                ctx.arc(p.x, p.y, s, 0, TAU)
                ctx.fillStyle = `hsla(${hue + k * 120},90%,70%,${0.2 + 0.6 * k})`
                ctx.fill()
            }
        }
    }

    class TextWave
    {
        constructor()
        {
            this.text = 'EMERGENT ORBITAL DREAMING'
            this.points = []
            this.hue = rand(0, 360)
            this.ready = false
            this.offscreen = document.createElement('canvas')
            this.octx = this.offscreen.getContext('2d')
            this.sample()
        }
        sample()
        {
            this.offscreen.width = 800
            this.offscreen.height = 200
            this.octx.clearRect(0, 0, this.offscreen.width, this.offscreen.height)
            this.octx.fillStyle = '#000'
            this.octx.fillRect(0, 0, this.offscreen.width, this.offscreen.height)
            this.octx.font = 'bold 72px sans-serif'
            this.octx.textAlign = 'center'
            this.octx.textBaseline = 'middle'
            this.octx.fillStyle = '#fff'
            this.octx.fillText(this.text, this.offscreen.width / 2, this.offscreen.height / 2)
            const imageData = this.octx.getImageData(0, 0, this.offscreen.width, this.offscreen.height)
            this.points = []
            for (let y = 0; y < this.offscreen.height; y += 4)
            {
                for (let x = 0; x < this.offscreen.width; x += 4)
                {
                    const idx = (x + y * this.offscreen.width) * 4
                    const alpha = imageData.data[idx + 3]
                    if (alpha > 50)
                    {
                        this.points.push({
                            x: x - this.offscreen.width / 2,
                            y: y - this.offscreen.height / 2
                        })
                    }
                }
            }
            this.ready = true
        }
        draw(ctx, t)
        {
            if (!this.ready) return
            const centerX = width / 2
            const centerY = height * 0.2
            const time = t * 0.001
            const len = this.points.length
            for (let i = 0; i < len; i++)
            {
                const p = this.points[i]
                const k = i / len
                const wave = Math.sin(time * 2 + k * TAU * 4) * 8
                const px = centerX + p.x * 0.8 + Math.sin(time + k * 20) * 4
                const py = centerY + p.y * 0.8 + wave
                const s = 1 + Math.sin(time * 3 + k * TAU * 3) * 0.8
                const hue = this.hue + k * 120 + Math.sin(time * 0.5) * 60
                const alpha = 0.2 + 0.8 * smoothstep(0, 0.6, Math.abs(Math.sin(time + k * TAU)))
                ctx.beginPath()
                ctx.arc(px, py, s, 0, TAU)
                ctx.fillStyle = `hsla(${hue},90%,70%,${alpha})`
                ctx.fill()
            }
        }
    }

    const particles = []
    const attractors = []
    const orbs = []
    const ribbon = new Ribbon()
    const network = new PolygonNetwork(60)
    const textWave = new TextWave()

    const flowScale = 40
    const flowCols = Math.ceil(width / flowScale)
    const flowRows = Math.ceil(height / flowScale)
    const flow = new FlowField(flowCols, flowRows, flowScale)

    for (let i = 0; i < 3; i++)
    {
        orbs.push(new Orb())
    }

    const spawnParticle = (x, y) =>
    {
        particles.push(new Particle(x, y))
    }

    const spawnBurst = (x, y, count) =>
    {
        for (let i = 0; i < count; i++)
        {
            spawnParticle(x + rand(-10, 10), y + rand(-10, 10))
        }
    }

    const spawnAttractors = () =>
    {
        attractors.length = 0
        const count = 4
        for (let i = 0; i < count; i++)
        {
            const ax = rand(width * 0.1, width * 0.9)
            const ay = rand(height * 0.3, height * 0.9)
            const strength = rand(0.5, 2)
            attractors.push(new Attractor(ax, ay, strength))
        }
    }

    spawnAttractors()

    let lastTime = performance.now()
    let time = 0
    let hueBase = 0

    const modes = ['flow', 'orbs', 'network']
    let modeIndex = 0

    const nextMode = () =>
    {
        modeIndex = (modeIndex + 1) % modes.length
        spawnAttractors()
        for (let i = 0; i < 200; i++)
        {
            spawnParticle(rand(0, width), rand(0, height))
        }
    }

    window.addEventListener('keydown', e =>
    {
        if (e.key === ' ')
        {
            nextMode()
        }
        if (e.key === 'c')
        {
            ctx.clearRect(0, 0, width, height)
            particles.length = 0
            spawnAttractors()
        }
    })

    const drawBackground = (t, dt) =>
    {
        const fade = 0.12
        ctx.fillStyle = `rgba(5,5,15,${fade})`
        ctx.fillRect(0, 0, width, height)
        const grad = ctx.createLinearGradient(0, 0, width, height)
        const k = (Math.sin(t * 0.00015) + 1) * 0.5
        const h1 = hueBase + k * 60
        const h2 = hueBase + 120 + Math.sin(t * 0.00013) * 40
        grad.addColorStop(0, `hsla(${h1},50%,4%,0.3)`)
        grad.addColorStop(1, `hsla(${h2},60%,8%,0.4)`)
        ctx.fillStyle = grad
        ctx.fillRect(0, 0, width, height)
    }

    const drawMouseAura = (t) =>
    {
        const r = 140
        const grad = ctx.createRadialGradient(mouseX, mouseY, 0, mouseX, mouseY, r)
        const pulse = (Math.sin(t * 0.005) + 1) * 0.5
        const alpha = 0.2 + 0.3 * pulse
        grad.addColorStop(0, `hsla(${hueBase + pulse * 80},90%,70%,${alpha})`)
        grad.addColorStop(1, `hsla(${hueBase + 180},90%,30%,0)`)
        ctx.globalCompositeOperation = 'screen'
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(mouseX, mouseY, r, 0, TAU)
        ctx.fill()
        ctx.globalCompositeOperation = 'lighter'
    }

    const updateParticles = (dt) =>
    {
        const mode = modes[modeIndex]
        const globalTarget = { x: width / 2, y: height / 2 }
        const dtSec = dt
        const baseCount = 6
        if (mouseDown)
        {
            const speed = Math.max(2, Math.min(60, Math.floor(distVec({ x: mouseX, y: mouseY }, { x: pmouseX, y: pmouseY }) / 2)))
            for (let i = 0; i < speed; i++)
            {
                spawnParticle(mouseX, mouseY)
            }
        }
        else
        {
            for (let i = 0; i < baseCount; i++)
            {
                const ang = rand(0, TAU)
                const d = rand(80, 200)
                const x = globalTarget.x + Math.cos(ang) * d
                const y = globalTarget.y + Math.sin(ang) * d
                spawnParticle(x, y)
            }
        }
        flow.update(dtSec)
        for (let i = particles.length - 1; i >= 0; i--)
        {
            const p = particles[i]
            p.follow(flow)
            for (let a of attractors)
            {
                a.applyTo(p)
            }
            if (mode === 'orbs')
            {
                for (let o of orbs)
                {
                    const d = distVec(p.pos, o.center)
                    if (d < o.radius * 1.2)
                    {
                        const dir = { x: p.pos.x - o.center.x, y: p.pos.y - o.center.y }
                        const l = lengthVec(dir) || 1
                        dir.x /= l
                        dir.y /= l
                        mulVec(dir, 0.04)
                        p.applyForce(dir)
                        p.hue = lerp(p.hue, o.hue, 0.02)
                    }
                }
            }
            const noiseForce = {
                x: Math.sin(time * 0.0002 + p.noiseOffset) * 0.02,
                y: Math.cos(time * 0.00018 + p.noiseOffset * 0.7) * 0.02
            }
            p.applyForce(noiseForce)
            p.update(dtSec)
            if (p.isDead())
            {
                particles.splice(i, 1)
            }
        }
    }

    const drawParticles = () =>
    {
        const mode = modes[modeIndex]
        const blend = mode === 'network' ? 'screen' : 'lighter'
        ctx.globalCompositeOperation = blend
        for (let p of particles)
        {
            p.drawTrail(ctx)
        }
        ctx.globalCompositeOperation = 'screen'
        for (let p of particles)
        {
            p.draw(ctx)
        }
    }

    const drawAttractors = (t) =>
    {
        ctx.globalCompositeOperation = 'screen'
        for (let a of attractors)
        {
            a.draw(ctx, t)
        }
    }

    const updateOrbs = (dt, t) =>
    {
        for (let o of orbs)
        {
            o.update(dt, t)
        }
    }

    const drawOrbs = (t) =>
    {
        ctx.globalCompositeOperation = 'screen'
        for (let o of orbs)
        {
            o.draw(ctx, t)
        }
    }

    const updateNetwork = (dt, t) =>
    {
        network.update(dt, t)
    }

    const drawNetwork = (t) =>
    {
        ctx.globalCompositeOperation = 'screen'
        network.draw(ctx, t)
    }

    const updateRibbon = (dt, t) =>
    {
        ribbon.update(dt, t)
    }

    const drawRibbon = (t) =>
    {
        ctx.globalCompositeOperation = 'screen'
        ribbon.draw(ctx, t)
    }

    const drawTextWave = (t) =>
    {
        ctx.globalCompositeOperation = 'screen'
        textWave.draw(ctx, t)
    }

    const loop = (now) =>
    {
        const dt = now - lastTime
        lastTime = now
        time += dt
        hueBase += dt * 0.002
        drawBackground(time, dt)
        updateParticles(dt)
        const mode = modes[modeIndex]
        updateOrbs(dt, time)
        updateNetwork(dt, time)
        updateRibbon(dt, time)
        drawParticles()
        drawAttractors(time)
        if (mode === 'orbs')
        {
            drawOrbs(time)
        }
        if (mode === 'network')
        {
            drawNetwork(time)
        }
        drawRibbon(time)
        drawTextWave(time)
        drawMouseAura(time)
        requestAnimationFrame(loop)
    }

    for (let i = 0; i < 400; i++)
    {
        spawnParticle(rand(0, width), rand(0, height))
    }

    requestAnimationFrame(loop)
})()
