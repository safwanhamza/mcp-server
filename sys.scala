/**
 * __________________________________________________________________
 * |                                                                  |
 * |   SYSTEM:  OMEGA-7 DISTRIBUTED NEURAL SIMULATION KERNEL          |
 * |   VERSION: 4.2.1-RC3                                             |
 * |   STATUS:  EXPERIMENTAL                                          |
 * |__________________________________________________________________|
 *
 */

import scala.collection.mutable
import scala.util.{Try, Success, Failure, Random}
import java.util.UUID
import java.time.Instant
import scala.concurrent.{Future, ExecutionContext, Promise, Await}
import scala.concurrent.duration._
import java.util.concurrent.atomic.AtomicLong

// =================================================================================================
// SECTION 1: CORE UTILITIES & LOGGING
// =================================================================================================

object CoreUtils {
  val SystemEpoch: Long = Instant.now().toEpochMilli
  private val idCounter = new AtomicLong(0)

  def generateUID(): String = {
    val id = idCounter.incrementAndGet()
    f"UID-$id%08d-${UUID.randomUUID().toString.take(8)}"
  }

  def clamp(v: Double, min: Double, max: Double): Double = Math.max(min, Math.min(max, v))
  
  def sigmoid(x: Double): Double = 1.0 / (1.0 + Math.exp(-x))
  def derivativeSigmoid(x: Double): Double = {
    val s = sigmoid(x)
    s * (1 - s)
  }
  
  def relu(x: Double): Double = Math.max(0, x)
}

sealed trait LogLevel
case object DEBUG extends LogLevel
case object INFO extends LogLevel
case object WARN extends LogLevel
case object ERROR extends LogLevel
case object CRITICAL extends LogLevel

object Logger {
  private var history: List[String] = List.empty
  private val MaxHistory = 1000

  def log(level: LogLevel, component: String, msg: String): Unit = {
    val timestamp = Instant.now().toString
    val color = level match {
      case DEBUG => "\u001B[36m" // Cyan
      case INFO  => "\u001B[32m" // Green
      case WARN  => "\u001B[33m" // Yellow
      case ERROR => "\u001B[31m" // Red
      case CRITICAL => "\u001B[35m" // Magenta
    }
    val reset = "\u001B[0m"
    val formatted = f"$color[$timestamp] [$level%-5s] [$component%-15s]: $msg$reset"
    
    println(formatted)
    synchronized {
      history = (formatted :: history).take(MaxHistory)
    }
  }
  
  def dump(): Unit = synchronized { history.reverse.foreach(println) }
}

// =================================================================================================
// SECTION 2: LINEAR ALGEBRA ENGINE
// =================================================================================================

case class Vector3(x: Double, y: Double, z: Double) {
  def +(o: Vector3): Vector3 = Vector3(x + o.x, y + o.y, z + o.z)
  def -(o: Vector3): Vector3 = Vector3(x - o.x, y - o.y, z - o.z)
  def *(s: Double): Vector3 = Vector3(x * s, y * s, z * s)
  def /(s: Double): Vector3 = if (s != 0) Vector3(x / s, y / s, z / s) else Vector3(0,0,0)
  
  def dot(o: Vector3): Double = x * o.x + y * o.y + z * o.z
  def cross(o: Vector3): Vector3 = Vector3(
    y * o.z - z * o.y,
    z * o.x - x * o.z,
    x * o.y - y * o.x
  )
  
  def magnitude: Double = Math.sqrt(x*x + y*y + z*z)
  def normalize: Vector3 = {
    val m = magnitude
    if (m > 0) this / m else this
  }
  
  def distanceTo(o: Vector3): Double = (this - o).magnitude

  override def toString: String = f"Vec3($x%.2f, $y%.2f, $z%.2f)"
}

case class Matrix3x3(rows: Array[Array[Double]]) {
  require(rows.length == 3 && rows.forall(_.length == 3))

  def *(v: Vector3): Vector3 = {
    Vector3(
      rows(0)(0)*v.x + rows(0)(1)*v.y + rows(0)(2)*v.z,
      rows(1)(0)*v.x + rows(1)(1)*v.y + rows(1)(2)*v.z,
      rows(2)(0)*v.x + rows(2)(1)*v.y + rows(2)(2)*v.z
    )
  }
  
  def *(o: Matrix3x3): Matrix3x3 = {
    val result = Array.ofDim[Double](3, 3)
    for (i <- 0 until 3; j <- 0 until 3) {
      var sum = 0.0
      for (k <- 0 until 3) sum += rows(i)(k) * o.rows(k)(j)
      result(i)(j) = sum
    }
    Matrix3x3(result)
  }
}

object MatrixFactory {
  def identity: Matrix3x3 = Matrix3x3(Array(
    Array(1.0, 0.0, 0.0),
    Array(0.0, 1.0, 0.0),
    Array(0.0, 0.0, 1.0)
  ))
  
  def rotationX(angle: Double): Matrix3x3 = {
    val c = Math.cos(angle)
    val s = Math.sin(angle)
    Matrix3x3(Array(
      Array(1.0, 0.0, 0.0),
      Array(0.0, c, -s),
      Array(0.0, s, c)
    ))
  }
  
  def rotationY(angle: Double): Matrix3x3 = {
    val c = Math.cos(angle)
    val s = Math.sin(angle)
    Matrix3x3(Array(
      Array(c, 0.0, s),
      Array(0.0, 1.0, 0.0),
      Array(-s, 0.0, c)
    ))
  }

  def rotationZ(angle: Double): Matrix3x3 = {
    val c = Math.cos(angle)
    val s = Math.sin(angle)
    Matrix3x3(Array(
      Array(c, -s, 0.0),
      Array(s, c, 0.0),
      Array(0.0, 0.0, 1.0)
    ))
  }
}

// =================================================================================================
// SECTION 3: NEURAL NETWORK ABSTRACTION
// =================================================================================================

sealed trait ActivationFunction {
  def apply(x: Double): Double
  def derivative(x: Double): Double
}

object Sigmoid extends ActivationFunction {
  def apply(x: Double): Double = CoreUtils.sigmoid(x)
  def derivative(x: Double): Double = CoreUtils.derivativeSigmoid(x)
}

object Tanh extends ActivationFunction {
  def apply(x: Double): Double = Math.tanh(x)
  def derivative(x: Double): Double = {
    val t = Math.tanh(x)
    1 - t * t
  }
}

class Neuron(val id: String, var weights: Array[Double], var bias: Double, activation: ActivationFunction) {
  var lastOutput: Double = 0.0
  var lastInput: Double = 0.0
  var delta: Double = 0.0 // Error term

  def forward(inputs: Array[Double]): Double = {
    require(inputs.length == weights.length, s"Input size ${inputs.length} mismatch with weight size ${weights.length}")
    var sum = bias
    for (i <- inputs.indices) {
      sum += inputs(i) * weights(i)
    }
    lastInput = sum
    lastOutput = activation(sum)
    lastOutput
  }
}

class Layer(val size: Int, inputSize: Int, activation: ActivationFunction) {
  val neurons: Array[Neuron] = Array.tabulate(size) { i =>
    val weights = Array.fill(inputSize)(Random.nextGaussian() * 0.1)
    new Neuron(f"N-$i", weights, Random.nextGaussian() * 0.1, activation)
  }

  def forward(inputs: Array[Double]): Array[Double] = {
    neurons.map(_.forward(inputs))
  }
}

class Network(topology: List[Int]) {
  val layers: Array[Layer] = {
    val builder = mutable.ArrayBuffer[Layer]()
    for (i <- 0 until topology.length - 1) {
      builder += new Layer(topology(i + 1), topology(i), Sigmoid)
    }
    builder.toArray
  }

  def predict(inputs: Array[Double]): Array[Double] = {
    var current = inputs
    for (layer <- layers) {
      current = layer.forward(current)
    }
    current
  }
  
  // Basic Backpropagation implementation
  def train(input: Array[Double], target: Array[Double], learningRate: Double): Double = {
    val outputs = predict(input) // This populates lastOutput in neurons
    
    // 1. Calculate output layer error
    val outputLayer = layers.last
    var totalError = 0.0
    
    for (i <- outputLayer.neurons.indices) {
      val neuron = outputLayer.neurons(i)
      val error = target(i) - neuron.lastOutput
      totalError += error * error
      neuron.delta = error * Sigmoid.derivative(neuron.lastInput)
    }

    // 2. Backpropagate hidden layers
    for (l <- layers.length - 2 to 0 by -1) {
      val currentLayer = layers(l)
      val nextLayer = layers(l + 1)
      
      for (j <- currentLayer.neurons.indices) {
        val neuron = currentLayer.neurons(j)
        var errorSum = 0.0
        for (k <- nextLayer.neurons.indices) {
          errorSum += nextLayer.neurons(k).delta * nextLayer.neurons(k).weights(j)
        }
        neuron.delta = errorSum * Sigmoid.derivative(neuron.lastInput)
      }
    }

    // 3. Update weights
    var previousOutputs = input
    for (l <- layers.indices) {
      val layer = layers(l)
      for (neuron <- layer.neurons) {
        for (w <- neuron.weights.indices) {
          neuron.weights(w) += learningRate * neuron.delta * previousOutputs(w)
        }
        neuron.bias += learningRate * neuron.delta
      }
      previousOutputs = layer.neurons.map(_.lastOutput)
    }
    
    totalError
  }
  
  def serialize: String = {
    layers.zipWithIndex.map { case (layer, lIdx) =>
      s"Layer $lIdx:\n" + layer.neurons.map(n => s"  Bias: ${n.bias}, W: [${n.weights.mkString(",")}]").mkString("\n")
    }.mkString("\n")
  }
}

// =================================================================================================
// SECTION 4: GENOME & EVOLUTION
// =================================================================================================

case class Gene(code: String, value: Double)

class Genome(val genes: Map[String, Gene]) {
  def mutate(rate: Double, strength: Double): Genome = {
    val newGenes = genes.map { case (k, gene) =>
      if (Random.nextDouble() < rate) {
        k -> gene.copy(value = gene.value + Random.nextGaussian() * strength)
      } else {
        k -> gene
      }
    }
    new Genome(newGenes)
  }
  
  def crossover(other: Genome): Genome = {
    val keys = genes.keySet ++ other.genes.keySet
    val newMap = keys.map { k =>
      val g = if (Random.nextBoolean()) genes.getOrElse(k, other.genes(k)) else other.genes.getOrElse(k, genes(k))
      k -> g
    }.toMap
    new Genome(newMap)
  }
}

object GenomeFactory {
  def random(size: Int): Genome = {
    val map = (0 until size).map { i =>
      val key = f"LOCUS-$i%03d"
      key -> Gene(UUID.randomUUID().toString.take(4), Random.nextDouble())
    }.toMap
    new Genome(map)
  }
}

// =================================================================================================
// SECTION 5: ENTITY COMPONENT SYSTEM (ECS)
// =================================================================================================

type EntityID = String

sealed trait Component
case class TransformComponent(var position: Vector3, var rotation: Vector3, var scale: Vector3) extends Component
case class VelocityComponent(var linear: Vector3, var angular: Vector3) extends Component
case class RenderComponent(meshId: String, visible: Boolean, colorHex: Int) extends Component
case class AIComponent(network: Network, genome: Genome, generation: Int) extends Component
case class HealthComponent(var current: Double, max: Double) extends Component
case class InventoryComponent(items: mutable.ListBuffer[String], capacity: Int) extends Component
case class TagComponent(tags: Set[String]) extends Component

class Entity(val id: EntityID) {
  private val components = mutable.Map[Class[_], Component]()

  def add(c: Component): this.type = {
    components(c.getClass) = c
    this
  }

  def get[T <: Component](implicit tag: scala.reflect.ClassTag[T]): Option[T] = {
    components.get(tag.runtimeClass).map(_.asInstanceOf[T])
  }
  
  def has[T <: Component](implicit tag: scala.reflect.ClassTag[T]): Boolean = {
    components.contains(tag.runtimeClass)
  }

  def remove[T <: Component](implicit tag: scala.reflect.ClassTag[T]): Unit = {
    components.remove(tag.runtimeClass)
  }
  
  def allComponents: List[Component] = components.values.toList
}

class World {
  private val entities = mutable.Map[EntityID, Entity]()
  private val systems = mutable.ListBuffer[System]()
  var tick: Long = 0

  def createEntity(): Entity = {
    val e = new Entity(CoreUtils.generateUID())
    entities(e.id) = e
    e
  }

  def removeEntity(id: EntityID): Unit = entities.remove(id)
  
  def getEntity(id: EntityID): Option[Entity] = entities.get(id)
  
  def getAllEntities: List[Entity] = entities.values.toList

  def addSystem(s: System): Unit = systems += s

  def update(dt: Double): Unit = {
    tick += 1
    systems.foreach(_.update(this, dt))
  }
  
  def query[T <: Component](implicit tag: scala.reflect.ClassTag[T]): List[(Entity, T)] = {
    entities.values.flatMap(e => e.get[T].map(c => (e, c))).toList
  }
}

trait System {
  def update(world: World, dt: Double): Unit
}

// -------------------------------------------------------------------------------------------------
// SPECIFIC SYSTEMS
// -------------------------------------------------------------------------------------------------

class PhysicsSystem extends System {
  override def update(world: World, dt: Double): Unit = {
    val moving = world.query[VelocityComponent]
    
    for ((entity, vel) <- moving) {
      entity.get[TransformComponent].foreach { trans =>
        trans.position = trans.position + (vel.linear * dt)
        trans.rotation = trans.rotation + (vel.angular * dt)
        
        // Basic bounds checking (Universe limit)
        if (trans.position.magnitude > 1000.0) {
           vel.linear = vel.linear * -0.5 // Bounce back
           trans.position = trans.position.normalize * 999.0
           Logger.log(DEBUG, "PHYSICS", s"Entity ${entity.id} hit world boundary.")
        }
      }
    }
  }
}

class AISystem extends System {
  override def update(world: World, dt: Double): Unit = {
    // Only run AI logic every 10 ticks to save "cpu"
    if (world.tick % 10 != 0) return

    val agents = world.query[AIComponent]
    
    for ((entity, ai) <- agents) {
      entity.get[TransformComponent].foreach { trans =>
        // Sensory inputs: Position (x,y,z) + Random Noise
        val inputs = Array(
          trans.position.x / 1000.0,
          trans.position.y / 1000.0,
          trans.position.z / 1000.0,
          Random.nextDouble()
        )
        
        val decision = ai.network.predict(inputs)
        
        // Output interpretation: 0->SpeedX, 1->SpeedY, 2->SpeedZ
        entity.get[VelocityComponent].foreach { vel =>
          val thrust = Vector3(
            decision(0) - 0.5, 
            decision(1) - 0.5, 
            decision(2) - 0.5
          ) * 10.0
          
          vel.linear = vel.linear + (thrust * dt)
          // Dampening
          vel.linear = vel.linear * 0.98
        }
        
        // Energy cost for thinking
        entity.get[HealthComponent].foreach { health =>
          health.current -= 0.01
          if (health.current <= 0) {
             Logger.log(INFO, "AI_SYS", s"Entity ${entity.id} died of exhaustion.")
             // In a real system we'd queue removal, but let's just mark it for now
             entity.remove[AIComponent] // Lobotomy
          }
        }
      }
    }
  }
}

class RenderSystem extends System {
  override def update(world: World, dt: Double): Unit = {
    if (world.tick % 60 != 0) return // Render once per second simulated
    val renderables = world.query[RenderComponent]
    Logger.log(DEBUG, "RENDER", s"Rendering ${renderables.size} entities active frame ${world.tick}")
  }
}

// =================================================================================================
// SECTION 6: COMMAND INTERPRETER & SCRIPTING
// =================================================================================================

sealed trait Command
case class CmdSpawn(count: Int, archetype: String) extends Command
case class CmdKill(id: String) extends Command
case class CmdQuery(filter: String) extends Command
case class CmdStatus() extends Command
case class CmdTrain(iterations: Int) extends Command
case object CmdExit extends Command

object CommandParser {
  def parse(input: String): Try[Command] = {
    val tokens = input.trim.split("\\s+")
    tokens.headOption.map(_.toUpperCase) match {
      case Some("SPAWN") => 
        if (tokens.length >= 3) Success(CmdSpawn(tokens(1).toInt, tokens(2)))
        else Failure(new IllegalArgumentException("Usage: SPAWN <count> <type>"))
      
      case Some("KILL") =>
        if (tokens.length >= 2) Success(CmdKill(tokens(1)))
        else Failure(new IllegalArgumentException("Usage: KILL <id>"))
        
      case Some("QUERY") =>
        Success(CmdQuery(tokens.drop(1).mkString(" ")))
        
      case Some("STATUS") => Success(CmdStatus())
      
      case Some("TRAIN") =>
        if (tokens.length >= 2) Success(CmdTrain(tokens(1).toInt))
        else Success(CmdTrain(1))

      case Some("EXIT") | Some("QUIT") => Success(CmdExit)
      
      case Some(x) => Failure(new IllegalArgumentException(s"Unknown command: $x"))
      case None => Failure(new IllegalArgumentException("Empty command"))
    }
  }
}

// =================================================================================================
// SECTION 7: EVENT BUS & MESSAGING
// =================================================================================================

sealed trait GameEvent
case class EntityCreated(id: String, timestamp: Long) extends GameEvent
case class EntityDestroyed(id: String, reason: String) extends GameEvent
case class CollisionEvent(a: String, b: String, impact: Double) extends GameEvent
case class SystemAlert(level: String, msg: String) extends GameEvent

object EventBus {
  private val subscribers = mutable.ListBuffer[GameEvent => Unit]()
  private val queue = mutable.Queue[GameEvent]()
  
  def subscribe(callback: GameEvent => Unit): Unit = {
    subscribers += callback
  }
  
  def publish(e: GameEvent): Unit = {
    queue.enqueue(e)
  }
  
  def process(): Unit = {
    while (queue.nonEmpty) {
      val event = queue.dequeue()
      subscribers.foreach(safeCall(_, event))
    }
  }
  
  private def safeCall(cb: GameEvent => Unit, e: GameEvent): Unit = {
    try { cb(e) } catch {
      case ex: Exception => Logger.log(ERROR, "EVENTBUS", s"Subscriber failed: ${ex.getMessage}")
    }
  }
}

// =================================================================================================
// SECTION 8: NETWORK SIMULATION (VIRTUAL PACKETS)
// =================================================================================================

case class PacketHeader(src: String, dest: String, seq: Int, protocol: Int)
case class Packet(header: PacketHeader, payload: Array[Byte], checksum: Long)

class NetworkInterface(val address: String, world: World) {
  private val buffer = mutable.Queue[Packet]()
  
  def send(dest: String, data: String): Unit = {
    val bytes = data.getBytes("UTF-8")
    val p = Packet(
      PacketHeader(address, dest, Random.nextInt(), 1),
      bytes,
      calculateChecksum(bytes)
    )
    // Simulate latency
    Logger.log(INFO, "NET_IF", s"Sending ${bytes.length} bytes to $dest from $address")
    NetworkSim.route(p)
  }
  
  def receive(p: Packet): Unit = {
    if (validate(p)) {
      buffer.enqueue(p)
      Logger.log(DEBUG, "NET_IF", s"Received packet from ${p.header.src}")
    } else {
      Logger.log(WARN, "NET_IF", s"Corrupted packet dropped from ${p.header.src}")
    }
  }
  
  private def calculateChecksum(data: Array[Byte]): Long = data.map(_.toLong).sum
  private def validate(p: Packet): Boolean = calculateChecksum(p.payload) == p.checksum
}

object NetworkSim {
  private val interfaces = mutable.Map[String, NetworkInterface]()
  
  def register(ni: NetworkInterface): Unit = {
    interfaces(ni.address) = ni
  }
  
  def route(p: Packet): Unit = {
    // 10% packet loss simulation
    if (Random.nextDouble() > 0.90) {
      Logger.log(WARN, "NET_SIM", "Packet lost in transit")
      return
    }
    
    // Async delivery simulation
    Future {
      Thread.sleep((Random.nextDouble() * 100).toLong) // Network jitter
      if (interfaces.contains(p.header.dest)) {
        interfaces(p.header.dest).receive(p)
      } else {
        Logger.log(ERROR, "NET_SIM", s"Destination host unreachable: ${p.header.dest}")
      }
    }(ExecutionContext.global)
  }
}

// =================================================================================================
// SECTION 9: VIRTUAL FILE SYSTEM
// =================================================================================================

sealed trait VNode
case class VFile(name: String, content: Array[Byte], permissions: Int) extends VNode
case class VDir(name: String, children: mutable.Map[String, VNode]) extends VNode

class VFS {
  val root = VDir("/", mutable.Map())
  
  def touch(path: String, content: String): Unit = {
    val parts = path.split("/").filter(_.nonEmpty)
    var current = root
    
    // Navigate to parent
    for (i <- 0 until parts.length - 1) {
      current.children.get(parts(i)) match {
        case Some(d: VDir) => current = d
        case _ => 
          val newDir = VDir(parts(i), mutable.Map())
          current.children(parts(i)) = newDir
          current = newDir
      }
    }
    
    val fileName = parts.last
    current.children(fileName) = VFile(fileName, content.getBytes, 644)
    Logger.log(INFO, "VFS", s"Created file: $path")
  }
  
  def read(path: String): Option[String] = {
    val parts = path.split("/").filter(_.nonEmpty)
    var current: VNode = root
    
    for (part <- parts) {
      current match {
        case d: VDir => 
          d.children.get(part) match {
            case Some(node) => current = node
            case None => return None
          }
        case _ => return None
      }
    }
    
    current match {
      case f: VFile => Some(new String(f.content))
      case _ => None
    }
  }
  
  def tree(node: VNode = root, indent: String = ""): Unit = {
    node match {
      case VFile(name, _, _) => println(s"$indent- $name [FILE]")
      case VDir(name, children) => 
        println(s"$indent+ $name [DIR]")
        children.values.foreach(c => tree(c, indent + "  "))
    }
  }
}

// =================================================================================================
// SECTION 10: DATA PERSISTENCE SIMULATION (B-TREE MOCK)
// =================================================================================================

// Minimal BTree Node implementation
case class DBNode[K, V](
  var keys: mutable.ArrayBuffer[K],
  var values: mutable.ArrayBuffer[V],
  var children: mutable.ArrayBuffer[DBNode[K, V]],
  var isLeaf: Boolean
)(implicit ord: Ordering[K])

class InMemoryDB[K, V](order: Int)(implicit ord: Ordering[K]) {
  private var root: DBNode[K, V] = createNode(isLeaf = true)
  
  private def createNode(isLeaf: Boolean): DBNode[K, V] = 
    DBNode(mutable.ArrayBuffer(), mutable.ArrayBuffer(), mutable.ArrayBuffer(), isLeaf)

  def insert(key: K, value: V): Unit = {
    if (root.keys.size == (2 * order) - 1) {
      val s = createNode(isLeaf = false)
      s.children += root
      splitChild(s, 0)
      root = s
      insertNonFull(s, key, value)
    } else {
      insertNonFull(root, key, value)
    }
  }
  
  private def splitChild(x: DBNode[K, V], i: Int): Unit = {
    val y = x.children(i)
    val z = createNode(y.isLeaf)
    
    // Move last (order - 1) keys of y to z
    z.keys ++= y.keys.takeRight(order - 1)
    z.values ++= y.values.takeRight(order - 1)
    
    y.keys.dropRightInPlace(order - 1)
    y.values.dropRightInPlace(order - 1)
    
    if (!y.isLeaf) {
      z.children ++= y.children.takeRight(order)
      y.children.dropRightInPlace(order)
    }
    
    x.children.insert(i + 1, z)
    x.keys.insert(i, y.keys.last)
    x.values.insert(i, y.values.last)
    
    y.keys.dropRightInPlace(1)
    y.values.dropRightInPlace(1)
  }
  
  private def insertNonFull(x: DBNode[K, V], k: K, v: V): Unit = {
    var i = x.keys.size - 1
    if (x.isLeaf) {
      while (i >= 0 && ord.gt(x.keys(i), k)) { i -= 1 }
      x.keys.insert(i + 1, k)
      x.values.insert(i + 1, v)
    } else {
      while (i >= 0 && ord.gt(x.keys(i), k)) { i -= 1 }
      i += 1
      if (x.children(i).keys.size == (2 * order) - 1) {
        splitChild(x, i)
        if (ord.gt(k, x.keys(i))) i += 1
      }
      insertNonFull(x.children(i), k, v)
    }
  }
  
  def find(k: K): Option[V] = search(root, k)
  
  private def search(x: DBNode[K, V], k: K): Option[V] = {
    var i = 0
    while (i < x.keys.size && ord.gt(k, x.keys(i))) i += 1
    if (i < x.keys.size && ord.equiv(k, x.keys(i))) Some(x.values(i))
    else if (x.isLeaf) None
    else search(x.children(i), k)
  }
}

// =================================================================================================
// SECTION 11: JOB SCHEDULER
// =================================================================================================

trait Job {
  def id: String
  def priority: Int
  def execute(): Unit
}

class Scheduler(workerCount: Int) {
  private val queue = new java.util.concurrent.PriorityBlockingQueue[Job](100, 
    (a: Job, b: Job) => b.priority - a.priority)
    
  private val workers = (1 to workerCount).map { i =>
    new Thread(() => {
      while (!Thread.currentThread().isInterrupted) {
        try {
          val job = queue.take()
          Logger.log(DEBUG, s"WORKER-$i", s"Starting job ${job.id}")
          val start = System.nanoTime()
          job.execute()
          val duration = (System.nanoTime() - start) / 1000000.0
          Logger.log(DEBUG, s"WORKER-$i", f"Finished job ${job.id} in $duration%.2f ms")
        } catch {
          case _: InterruptedException => Thread.currentThread().interrupt()
          case e: Exception => Logger.log(ERROR, s"WORKER-$i", s"Job failed: ${e.getMessage}")
        }
      }
    })
  }
  
  def start(): Unit = workers.foreach(_.start())
  
  def submit(j: Job): Unit = {
    queue.offer(j)
    Logger.log(DEBUG, "SCHED", s"Submitted job ${j.id} (Pri: ${j.priority})")
  }
  
  def shutdown(): Unit = workers.foreach(_.interrupt())
}

// =================================================================================================
// SECTION 12: CONFIGURATION PARSER (CUSTOM FORMAT)
// =================================================================================================

// Format: KEY=VALUE; GROUP { K=V; }
case class ConfigNode(values: Map[String, String], children: Map[String, ConfigNode])

object ConfigLoader {
  def parse(source: String): ConfigNode = {
    // A very naive recursive descent parser
    var pos = 0
    val input = source.toCharArray
    
    def eatWhitespace(): Unit = {
      while (pos < input.length && Character.isWhitespace(input(pos))) pos += 1
    }
    
    def readIdentifier(): String = {
      val start = pos
      while (pos < input.length && (Character.isLetterOrDigit(input(pos)) || input(pos) == '_')) pos += 1
      new String(input, start, pos - start)
    }
    
    def readValue(): String = {
      val start = pos
      while (pos < input.length && input(pos) != ';' && input(pos) != '}') pos += 1
      new String(input, start, pos - start).trim
    }
    
    def parseBlock(): ConfigNode = {
      var vals = Map[String, String]()
      var kids = Map[String, ConfigNode]()
      
      while (pos < input.length && input(pos) != '}') {
        eatWhitespace()
        if (pos >= input.length || input(pos) == '}') return ConfigNode(vals, kids)
        
        val key = readIdentifier()
        eatWhitespace()
        
        if (pos < input.length) {
          if (input(pos) == '=') {
            pos += 1 // skip =
            val value = readValue()
            vals += (key -> value)
            if (pos < input.length && input(pos) == ';') pos += 1
          } else if (input(pos) == '{') {
            pos += 1 // skip {
            kids += (key -> parseBlock())
            if (pos < input.length && input(pos) == '}') pos += 1
          }
        }
      }
      ConfigNode(vals, kids)
    }
    
    parseBlock()
  }
}

// =================================================================================================
// SECTION 13: MAIN SIMULATION ORCHESTRATOR
// =================================================================================================

object SimulationEngine {
  val world = new World()
  val vfs = new VFS()
  val db = new InMemoryDB[String, String](4)
  val scheduler = new Scheduler(2)
  
  // Initialization
  def init(): Unit = {
    Logger.log(INFO, "BOOT", "Initializing OMEGA-7 Kernel...")
    
    // Add Systems
    world.addSystem(new PhysicsSystem())
    world.addSystem(new AISystem())
    world.addSystem(new RenderSystem())
    
    // Init Networking
    NetworkSim.register(new NetworkInterface("192.168.1.10", world))
    
    // Init Filesystem
    vfs.touch("/sys/config/boot.cfg", "MODE=HEADLESS; DEBUG=TRUE;")
    vfs.touch("/usr/local/readme.txt", "Welcome to the simulation.")
    
    // Init Scheduler
    scheduler.start()
    
    Logger.log(INFO, "BOOT", "Systems Online.")
  }
  
  // Entity Factory methods
  def spawnDrone(pos: Vector3): Entity = {
    val e = world.createEntity()
    e.add(TransformComponent(pos, Vector3(0,0,0), Vector3(1,1,1)))
     .add(VelocityComponent(Vector3(0,0,0), Vector3(0,0,0)))
     .add(HealthComponent(100.0, 100.0))
     .add(RenderComponent("drone_mesh", true, 0xFF0000))
     
    // Add AI Brain
    val net = new Network(List(4, 8, 8, 3)) // 4 in, 2 hidden layers, 3 out
    e.add(AIComponent(net, GenomeFactory.random(10), 0))
    
    EventBus.publish(EntityCreated(e.id, CoreUtils.SystemEpoch))
    e
  }
  
  def spawnStaticBlock(pos: Vector3): Entity = {
    val e = world.createEntity()
    e.add(TransformComponent(pos, Vector3(0,0,0), Vector3(2,2,2)))
     .add(RenderComponent("block_mesh", true, 0x888888))
     .add(TagComponent(Set("static", "obstacle")))
    e
  }
  
  // Simulation Loop
  def run(cycles: Int): Unit = {
    var c = 0
    val dt = 0.016 // 60 FPS
    
    while (c < cycles) {
      val start = System.nanoTime()
      
      // 1. Input Handling (Mock)
      // 2. Logic Update
      world.update(dt)
      
      // 3. Event Processing
      EventBus.process()
      
      // 4. Maintenance
      if (c % 100 == 0) {
        // Auto-save state to DB
        val state = f"CYCLE=$c; ENTITIES=${world.getAllEntities.size}"
        db.insert(f"snapshot_$c%05d", state)
      }
      
      val frameTime = (System.nanoTime() - start) / 1000000.0
      if (c % 60 == 0) {
        Logger.log(INFO, "CORE", f"Cycle $c completed in $frameTime%.2f ms. Entities: ${world.getAllEntities.size}")
      }
      
      c += 1
      
      // Simulate frame cap
      if (frameTime < 16.0) {
        try { Thread.sleep((16.0 - frameTime).toLong) } catch { case _: InterruptedException => }
      }
    }
  }
  
  def shutdown(): Unit = {
    Logger.log(WARN, "BOOT", "Shutting down...")
    scheduler.shutdown()
    Logger.log(INFO, "BOOT", "Goodbye.")
  }
}

// =================================================================================================
// SECTION 14: ENTRY POINT
// =================================================================================================

object Main {
  def main(args: Array[String]): Unit = {
    println("========================================")
    println("   SCALA COMPLEX SYSTEM SIMULATION      ")
    println("========================================")
    
    SimulationEngine.init()
    
    // Scripted Scenario
    Logger.log(INFO, "SCRIPT", "Spawning initial population...")
    for (i <- 1 to 20) {
      val x = Random.nextDouble() * 100 - 50
      val y = Random.nextDouble() * 100 - 50
      val z = Random.nextDouble() * 100 - 50
      SimulationEngine.spawnDrone(Vector3(x, y, z))
    }
    
    SimulationEngine.spawnStaticBlock(Vector3(0,0,0))
    
    // Run heavy computation job in background
    SimulationEngine.scheduler.submit(new Job {
      val id = "COMPUTE-PI"
      val priority = 1
      def execute(): Unit = {
        var acc = 0.0
        for (i <- 0 until 1000000) {
           acc += Math.pow(-1, i) / (2 * i + 1)
        }
        Logger.log(INFO, "JOB", s"Pi approx: ${acc * 4}")
      }
    })

    // Interactive CLI Loop (Mocked via list of commands for this non-interactive execution)
    val commandQueue = List(
      "STATUS",
      "SPAWN 5 DRONE",
      "QUERY tag=obstacle",
      "TRAIN 50",
      "WAIT",
      "KILL UID-001",
      "EXIT"
    )
    
    // Execute commands
    commandQueue.foreach { cmdStr =>
      Logger.log(INFO, "CLI", s"> $cmdStr")
      CommandParser.parse(cmdStr) match {
        case Success(cmd) => 
          cmd match {
            case CmdSpawn(n, t) => 
              Logger.log(INFO, "CMD", s"Spawning $n of $t")
              for(_ <- 1 to n) SimulationEngine.spawnDrone(Vector3(0,10,0))
            case CmdKill(id) =>
              SimulationEngine.world.removeEntity(id)
              Logger.log(INFO, "CMD", s"Removed $id")
            case CmdStatus() =>
              Logger.log(INFO, "CMD", s"System OK. Memory: ${Runtime.getRuntime.totalMemory()/1024/1024}MB")
            case CmdExit => Logger.log(INFO, "CMD", "Exit requested.")
            case _ => Logger.log(INFO, "CMD", "Command executed.")
          }
        case Failure(e) => Logger.log(ERROR, "CLI", e.getMessage)
      }
      Thread.sleep(200)
    }
    
    // Run main loop
    SimulationEngine.run(500) // Run 500 frames
    
    // Dump logs
    println("\n--- VFS DUMP ---")
    SimulationEngine.vfs.tree()
    
    println("\n--- DB SAMPLE ---")
    println(SimulationEngine.db.find("snapshot_00400").getOrElse("Not Found"))
    
    SimulationEngine.shutdown()
  }
}

// =================================================================================================
// SECTION 15: ADDITIONAL HELPERS AND EXTENSIONS
// =================================================================================================

// Extension methods for simpler math syntax
implicit class DoubleOps(d: Double) {
  def **(exp: Double): Double = Math.pow(d, exp)
  def clamp(min: Double, max: Double): Double = CoreUtils.clamp(d, min, max)
}

// Complex Number implementation for signal processing submodule
case class Complex(re: Double, im: Double) {
  def +(x: Complex): Complex = Complex(re + x.re, im + x.im)
  def -(x: Complex): Complex = Complex(re - x.re, im - x.im)
  def *(x: Complex): Complex = Complex(re * x.re - im * x.im, re * x.im + im * x.re)
  def abs: Double = Math.sqrt(re * re + im * im)
  override def toString: String = f"$re%.2f + ${im}%.2fi"
}

object FFT {
  def fft(a: Array[Complex]): Array[Complex] = {
    val n = a.length
    if (n == 1) return a
    
    val even = new Array[Complex](n / 2)
    val odd = new Array[Complex](n / 2)
    for (i <- 0 until n / 2) {
      even(i) = a(2 * i)
      odd(i) = a(2 * i + 1)
    }
    
    val q = fft(even)
    val r = fft(odd)
    val y = new Array[Complex](n)
    
    for (k <- 0 until n / 2) {
      val kth = -2 * Math.PI * k / n
      val wk = Complex(Math.cos(kth), Math.sin(kth))
      y(k) = q(k) + wk * r(k)
      y(k + n / 2) = q(k) - wk * r(k)
    }
    y
  }
}

// Genetic Algorithm Utility
object EvolutionStrategy {
  def selectFittest(population: List[Entity], count: Int): List[Entity] = {
    // Evaluate fitness based on distance from origin (just as an arbitrary goal)
    population.sortBy { e =>
      e.get[TransformComponent].map(_.position.magnitude).getOrElse(0.0)
    }.take(count) // Minimization problem
  }
  
  def breed(parents: List[Entity], targetSize: Int): List[Genome] = {
    val offspring = mutable.ListBuffer[Genome]()
    while(offspring.size < targetSize) {
      val p1 = parents(Random.nextInt(parents.size)).get[AIComponent].get.genome
      val p2 = parents(Random.nextInt(parents.size)).get[AIComponent].get.genome
      offspring += p1.crossover(p2).mutate(0.05, 0.1)
    }
    offspring.toList
  }
}

// Custom Exception Hierarchy
class SimException(msg: String) extends Exception(msg)
class ComponentNotFoundException(eId: String, cType: String) extends SimException(s"Entity $eId missing $cType")
class SystemCrashException(sys: String) extends SimException(s"System $sys has crashed critically")

// State Machine for Entity Behavior
sealed trait State { def update(e: Entity, w: World): State }

case object IdleState extends State {
  def update(e: Entity, w: World): State = {
    if (Random.nextDouble() < 0.01) PatrolState else this
  }
}

case object PatrolState extends State {
  def update(e: Entity, w: World): State = {
    e.get[VelocityComponent].foreach { vel =>
       vel.linear = Vector3(Random.nextDouble(), 0, Random.nextDouble()).normalize * 5.0
    }
    if (Random.nextDouble() < 0.05) IdleState else this
  }
}

// End of File
