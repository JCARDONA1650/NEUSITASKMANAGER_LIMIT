// neural-background.js - Fondo de red neural animada

class NeuralNetwork {
  constructor() {
    this.canvas = null;
    this.ctx = null;
    this.particles = [];
    this.animationId = null;
    this.mouse = { x: null, y: null, radius: 150 };
    
    this.init();
  }

  init() {
    // Crear canvas
    this.canvas = document.createElement('canvas');
    this.canvas.id = 'neural-canvas';
    this.canvas.style.position = 'fixed';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.zIndex = '-1';
    this.canvas.style.pointerEvents = 'none';
    
    document.body.insertBefore(this.canvas, document.body.firstChild);
    
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    this.createParticles();
    this.animate();
    
    // Event listeners
    window.addEventListener('resize', () => this.resize());
    window.addEventListener('mousemove', (e) => this.handleMouseMove(e));
  }

  resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  createParticles() {
    const numberOfParticles = Math.floor((this.canvas.width * this.canvas.height) / 15000);
    this.particles = [];
    
    for (let i = 0; i < numberOfParticles; i++) {
      this.particles.push(new Particle(
        Math.random() * this.canvas.width,
        Math.random() * this.canvas.height,
        this.canvas.width,
        this.canvas.height
      ));
    }
  }

  handleMouseMove(e) {
    this.mouse.x = e.x;
    this.mouse.y = e.y;
  }

  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    // Actualizar y dibujar partículas
    this.particles.forEach(particle => {
      particle.update(this.canvas.width, this.canvas.height);
      particle.draw(this.ctx);
    });
    
    // Conectar partículas cercanas
    this.connectParticles();
    
    this.animationId = requestAnimationFrame(() => this.animate());
  }

  connectParticles() {
    const maxDistance = 120;
    
    for (let i = 0; i < this.particles.length; i++) {
      for (let j = i + 1; j < this.particles.length; j++) {
        const dx = this.particles[i].x - this.particles[j].x;
        const dy = this.particles[i].y - this.particles[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < maxDistance) {
          // Opacidad basada en distancia
          const opacity = (1 - distance / maxDistance) * 0.35;
          
          this.ctx.strokeStyle = `rgba(182, 107, 255, ${opacity})`;
          this.ctx.lineWidth = 1;
          this.ctx.beginPath();
          this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
          this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
          this.ctx.stroke();
        }
      }
      
      // Conexión con el mouse
      if (this.mouse.x !== null && this.mouse.y !== null) {
        const dx = this.particles[i].x - this.mouse.x;
        const dy = this.particles[i].y - this.mouse.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < this.mouse.radius) {
          const opacity = (1 - distance / this.mouse.radius) * 0.5;
          this.ctx.strokeStyle = `rgba(182, 107, 255, ${opacity})`;
          this.ctx.lineWidth = 1.5;
          this.ctx.beginPath();
          this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
          this.ctx.lineTo(this.mouse.x, this.mouse.y);
          this.ctx.stroke();
        }
      }
    }
  }

  destroy() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
  }
}

class Particle {
  constructor(x, y, canvasWidth, canvasHeight) {
    this.x = x;
    this.y = y;
    this.size = Math.random() * 2 + 1;
    
    // Velocidad muy lenta para movimiento sutil
    this.speedX = (Math.random() - 0.5) * 0.3;
    this.speedY = (Math.random() - 0.5) * 0.3;
    
    // Dirección inicial
    this.directionX = this.speedX;
    this.directionY = this.speedY;
  }

  update(canvasWidth, canvasHeight) {
    // Movimiento
    this.x += this.directionX;
    this.y += this.directionY;
    
    // Rebote en los bordes
    if (this.x > canvasWidth || this.x < 0) {
      this.directionX = -this.directionX;
    }
    if (this.y > canvasHeight || this.y < 0) {
      this.directionY = -this.directionY;
    }
    
    // Mantener dentro del canvas
    if (this.x < 0) this.x = 0;
    if (this.x > canvasWidth) this.x = canvasWidth;
    if (this.y < 0) this.y = 0;
    if (this.y > canvasHeight) this.y = canvasHeight;
  }

  draw(ctx) {
    ctx.fillStyle = 'rgba(182, 107, 255, 0.8)';
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fill();
    
    // Glow effect
    ctx.shadowBlur = 10;
    ctx.shadowColor = 'rgba(182, 107, 255, 0.5)';
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  // Esperar un momento para asegurar que el body esté completamente cargado
  setTimeout(() => {
    window.neuralNetwork = new NeuralNetwork();
  }, 100);
});

// Limpiar al salir (opcional)
window.addEventListener('beforeunload', () => {
  if (window.neuralNetwork) {
    window.neuralNetwork.destroy();
  }
});