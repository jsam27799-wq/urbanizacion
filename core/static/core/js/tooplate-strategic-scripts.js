// Controla las interacciones de navegación, contenido dinámico y animaciones de la página pública.

// Tooplate 2149 Strategic Consulting

// https://www.tooplate.com/view/2149-strategic-consulting

// Abre o cierra el menú de navegación móvil y transforma las líneas del icono en una X.
const mobileMenu = document.querySelector('.mobile-menu');
const navLinks = document.querySelector('.nav-links');

mobileMenu.addEventListener('click', () => {
   navLinks.classList.toggle('active');

   // Ajusta cada línea del botón para reflejar visualmente el estado abierto o cerrado.
   const spans = mobileMenu.querySelectorAll('span');
   spans.forEach((span, index) => {
      span.style.transform = navLinks.classList.contains('active') ?
         (index === 0 ? 'rotate(45deg) translate(5px, 5px)' :
            index === 1 ? 'opacity(0)' :
            'rotate(-45deg) translate(7px, -6px)') : 'none';
   });
});

// Mantiene resaltado el enlace correspondiente a la sección que se encuentra en la ventana.
function updateActiveMenu() {
   const sections = document.querySelectorAll('section[id]');
   const navLinks = document.querySelectorAll('.nav-links a');

   let current = 'home'; // La página comienza asociada a su sección principal.

   // Evita cambiar la selección mientras la portada todavía ocupa la parte superior de la página.
   if (window.scrollY > 100) {
      sections.forEach(section => {
         const sectionTop = section.offsetTop;
         if (scrollY >= sectionTop - 200) {
            current = section.getAttribute('id');
         }
      });
   }

   navLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href').substring(1) === current) {
         link.classList.add('active');
      }
   });
}

window.addEventListener('scroll', updateActiveMenu);

// Al cargar la página, deja activo únicamente el enlace de inicio.
document.addEventListener('DOMContentLoaded', () => {
   const navLinks = document.querySelectorAll('.nav-links a');
   const homeLink = document.querySelector('.nav-links a[href="#home"]');

   // Limpia los estados anteriores para no mostrar varios enlaces activos.
   navLinks.forEach(link => link.classList.remove('active'));

   // Si existe el enlace a la portada, úsalo como selección inicial.
   if (homeLink) {
      homeLink.classList.add('active');
   }
});

updateActiveMenu();

// Alterna cada cinco segundos los mensajes destacados de la portada.
document.addEventListener('DOMContentLoaded', () => {
   const headline = document.getElementById('hero-headline');
   const paragraph = document.getElementById('hero-paragraph');

   if (headline && paragraph) {
      // Cada elemento mantiene emparejados el encabezado y su descripción.
      const textSets = [{
            h1: "Tus pagos automatizados",
            p: "Soportalos con la evidencia de pago"
         },
         {
            h1: "Brindamos seguridad a los residentes",
            p: "Control de acceso para visitantes, domiciliarios y paquetes"
         }
      ];

      let currentIndex = 0;

      // Alterna los textos destacados del encabezado con una transición de salida y entrada.
      function changeText() {
         // Oculta ambos textos antes de sustituirlos para que compartan la misma transición.
         headline.classList.add('text-fade-out');
         paragraph.classList.add('text-fade-out');

         setTimeout(() => {
            // El módulo recorre la lista y vuelve al principio al llegar al último mensaje.
            currentIndex = (currentIndex + 1) % textSets.length;

            // Sustituye el contenido de portada con el siguiente par de textos.
            headline.innerHTML = textSets[currentIndex].h1;
            paragraph.innerHTML = textSets[currentIndex].p;

            // Retira la clase de salida y permite que CSS vuelva a mostrar el contenido.
            headline.classList.remove('text-fade-out');
            paragraph.classList.remove('text-fade-out');
         }, 500); // Debe coincidir con la duración de transición definida en la hoja de estilos.
      }

      // Conserva cada mensaje visible durante cinco segundos antes de iniciar la transición siguiente.
      setInterval(changeText, 5000);
   }
});

// Conecta las pestañas de servicios con el panel de contenido seleccionado.
function initializeServiceTabs() {
   const serviceTabs = document.querySelectorAll('.service-tab');
   const serviceDetails = document.querySelectorAll('.service-details');

   if (!serviceTabs.length || !serviceDetails.length) return;

   // Activa una pestaña y presenta el contenido del servicio que eligió la persona.
   const activateService = (target) => {
      serviceTabs.forEach(tab => {
         const isActive = tab.getAttribute('data-target') === target;
         tab.classList.toggle('active', isActive);
         tab.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });

      serviceDetails.forEach(detail => {
         const isActive = detail.getAttribute('data-service') === target;
         detail.classList.toggle('active', isActive);
         detail.hidden = !isActive;
      });
   };

   serviceTabs.forEach(tab => {
      tab.setAttribute('aria-pressed', tab.classList.contains('active') ? 'true' : 'false');
      tab.addEventListener('click', () => {
         const target = tab.getAttribute('data-target');
         if (!target) return;
         activateService(target);
      });
   });

   const initialTarget = document.querySelector('.service-tab.active')?.getAttribute('data-target');
   if (initialTarget) {
      activateService(initialTarget);
   }
}

document.addEventListener('DOMContentLoaded', initializeServiceTabs);
initializeServiceTabs();

// Cambia la imagen y el texto descriptivo al seleccionar una característica de la sección informativa.
function initializeAboutFeatures() {
   const featureButtons = document.querySelectorAll('.feature-item[data-about-image]');
   const featureImage = document.getElementById('about-feature-image');
   const featureDescription = document.getElementById('about-feature-description');

   if (!featureButtons.length || !featureImage || !featureDescription) return;

   featureButtons.forEach(button => {
      button.addEventListener('click', () => {
         featureButtons.forEach(item => {
            const isActive = item === button;
            item.classList.toggle('active', isActive);
            item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
         });

         featureImage.classList.add('is-changing');
         window.setTimeout(() => {
            featureImage.src = button.dataset.aboutImage;
            featureImage.alt = button.dataset.aboutAlt || 'Residencia Piemonte';
            featureDescription.textContent = button.dataset.aboutDescription || '';
            featureImage.classList.remove('is-changing');
         }, 140);
      });
   });
}

document.addEventListener('DOMContentLoaded', initializeAboutFeatures);
initializeAboutFeatures();

// Revela las novedades que inicialmente se mantienen ocultas y quita el control cuando ya no hay más.
function initializeNewsGallery() {
   const hiddenNews = Array.from(document.querySelectorAll('.news-card-hidden'));
   const loadMoreButton = document.getElementById('load-more-news');
   if (!loadMoreButton) return;

   // Muestra el siguiente grupo de novedades y actualiza la disponibilidad de carga.
   const revealNews = () => {
      hiddenNews.splice(0).forEach(card => {
         card.classList.remove('news-card-hidden');
         card.classList.add('animate');
      });

      if (!hiddenNews.length) {
         loadMoreButton.remove();
      }
   };

   if (!hiddenNews.length) {
      loadMoreButton.remove();
      return;
   }

   loadMoreButton.addEventListener('click', revealNews);
}

document.addEventListener('DOMContentLoaded', initializeNewsGallery);
initializeNewsGallery();

// Muestra las reseñas adicionales y retira el botón que deja de ser necesario.
function initializeReviewsGallery() {
   const hiddenReviews = Array.from(document.querySelectorAll('.testimonial-hidden'));
   const loadMoreButton = document.getElementById('load-more-reviews');
   if (!loadMoreButton) return;

   loadMoreButton.addEventListener('click', () => {
      hiddenReviews.forEach(review => {
         review.classList.remove('testimonial-hidden');
         review.classList.add('animate');
      });
      loadMoreButton.remove();
   });
}

document.addEventListener('DOMContentLoaded', initializeReviewsGallery);
initializeReviewsGallery();

// Desplaza suavemente a las secciones enlazadas y cierra el menú móvil tras la navegación.
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
   anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
         target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
         });
      }
      navLinks.classList.remove('active');
   });
});

// Configura el umbral de visibilidad y el margen que activan las animaciones al entrar en pantalla.
const observerOptions = {
   threshold: 0.15,
   rootMargin: '0px 0px -100px 0px'
};

// Observa la entrada de elementos animados y activa la animación correspondiente.
const observer = new IntersectionObserver((entries) => {
   entries.forEach((entry, index) => {
      if (entry.isIntersecting) {
         setTimeout(() => {
            entry.target.classList.add('animate');

            // Los elementos contadores usan su animación numérica además de la transición visual.
            if (entry.target.classList.contains('counter')) {
               animateCounter(entry.target);
            }
         }, index * 100); // Desfase de 100 ms entre elementos para escalonar su aparición.
      }
   });
}, observerOptions);

// Registra los elementos que deben animarse o iniciar su contador al hacerse visibles.
document.querySelectorAll('.fade-in, .service-tab, .team-member, .testimonial, .counter').forEach(el => {
   observer.observe(el);
});

// Anima cada indicador una sola vez, incrementándolo hasta alcanzar su valor configurado.
function animateCounter(element) {
   if (element.classList.contains('animated')) return;
   element.classList.add('animated');

   const target = parseInt(element.getAttribute('data-count'));
   // Reparte el valor final en 80 pasos para completar el conteo gradualmente.
   const increment = target / 80;
   let current = 0;

   const timer = setInterval(() => {
      current += increment;
      const value = Math.floor(current);
      // Los indicadores mayores que 100 son cantidades; los demás se presentan como porcentajes.
      element.textContent = target > 100 ? value : value + '%';

      if (current >= target) {
         element.textContent = target > 100 ? target : target + '%';
         clearInterval(timer);
      }
   }, 25);
}

// Ajusta el borde de la barra de navegación según la posición de desplazamiento.
window.addEventListener('scroll', () => {
   const navbar = document.querySelector('.navbar');
   const scrolled = window.scrollY;

   if (scrolled > 50) {
      navbar.style.background = '#FFFFFF'; /* Mantiene un fondo blanco opaco al desplazarse. */
      navbar.style.borderBottomColor = 'rgba(71, 85, 105, 0.2)';
   } else {
      navbar.style.background = '#FFFFFF'; /* Conserva el mismo fondo antes de desplazarse. */
      navbar.style.borderBottomColor = 'rgba(71, 85, 105, 0.1)';
   }
});

// Presenta una confirmación visual local y reinicia el formulario de contacto tras la espera.
const contactForm = document.querySelector('.contact-form');
contactForm?.addEventListener('submit', (e) => {
   e.preventDefault();

   const submitBtn = contactForm.querySelector('.submit-btn');
   const originalText = submitBtn.textContent;

   submitBtn.textContent = 'Initiating Connection...';
   submitBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
   submitBtn.classList.add('loading');

   setTimeout(() => {
      submitBtn.textContent = 'Partnership Initiated!';
      submitBtn.classList.remove('loading');
      setTimeout(() => {
         submitBtn.textContent = originalText;
         submitBtn.style.background = 'linear-gradient(135deg, #64748b, #475569)';
         contactForm.reset();
      }, 3000);
   }, 2000);
});

// Da realce temporal a las pestañas inactivas mientras el puntero está sobre ellas.
document.querySelectorAll('.service-tab').forEach((tab, index) => {
   tab.addEventListener('mouseenter', () => {
      if (!tab.classList.contains('active')) {
         tab.style.transform = 'translateX(5px)';
         tab.style.boxShadow = '0 10px 25px rgba(71, 85, 105, 0.1)';
      }
   });

   tab.addEventListener('mouseleave', () => {
      if (!tab.classList.contains('active')) {
         tab.style.transform = 'translateX(0)';
         tab.style.boxShadow = 'none';
      }
   });
});

// Desplaza elementos decorativos a distintas velocidades para crear profundidad en la portada.
window.addEventListener('scroll', () => {
   const scrolled = window.pageYOffset;
   const parallaxElements = document.querySelectorAll('.geometric-shapes, .hero-content');

   parallaxElements.forEach((element, index) => {
      const speed = 0.3 + (index * 0.2);
      if (scrolled < window.innerHeight) {
         element.style.transform = `translateY(${scrolled * speed}px)`;
      }
   });

   // Aumenta el giro de cada figura en proporción a su posición y al desplazamiento de la página.
   const shapes = document.querySelectorAll('.geo-shape');
   shapes.forEach((shape, index) => {
      const rotation = scrolled * 0.05 * (index + 1);
      shape.style.transform += ` rotate(${rotation}deg)`;
   });
});

// Resalta cada reseña al pasar el puntero para distinguir el elemento enfocado.
document.querySelectorAll('.testimonial-content').forEach(testimonial => {
   testimonial.addEventListener('mouseenter', () => {
      testimonial.style.transform = 'scale(1.02) translateY(-5px)';
      testimonial.style.boxShadow = '0 25px 50px rgba(71, 85, 105, 0.2)';
   });

   testimonial.addEventListener('mouseleave', () => {
      testimonial.style.transform = 'scale(1) translateY(0)';
      testimonial.style.boxShadow = '0 15px 35px rgba(71, 85, 105, 0.1)';
   });
});