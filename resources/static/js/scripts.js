// Hub Canastra - JavaScript functionality
// Dependencies: None (Vanilla JS)

document.addEventListener('DOMContentLoaded', function () {
   // Initialize all components
   initFloatingTriangles();
   initMobileNavigation();
   initCarousel();
   initSmoothScroll();
   initSignupForm();
   initIntersectionObserver();
});

// ===== FLOATING TRIANGLES BACKGROUND =====
function initFloatingTriangles() {
   const container = document.getElementById('floating-triangles');
   if (!container) return;

   // Create floating triangles
   for (let i = 0; i < 8; i++) {
      const triangle = document.createElement('div');
      triangle.className = 'triangle';

      // Random positioning and sizing
      const size = Math.random() * 30 + 20;
      const x = Math.random() * 100;
      const y = Math.random() * 100;
      const delay = Math.random() * 6;

      triangle.style.cssText = `
            left: ${x}%;
            top: ${y}%;
            border-left: ${size / 2}px solid transparent;
            border-right: ${size / 2}px solid transparent;
            border-bottom: ${size * 0.866}px solid hsl(0, 84%, 60%);
            animation-delay: ${delay}s;
        `;

      container.appendChild(triangle);
   }
}

// ===== MOBILE NAVIGATION =====
function initMobileNavigation() {
   const mobileMenuBtn = document.getElementById('mobile-menu-btn');
   const mobileMenu = document.getElementById('mobile-menu');
   const navLinks = document.querySelectorAll('.nav-link');
   if (!mobileMenuBtn || !mobileMenu) return;

   // Toggle mobile menu
   mobileMenuBtn.addEventListener('click', function () {
      const isOpen = mobileMenu.classList.toggle('active');
      mobileMenuBtn.textContent = isOpen ? '✕' : '☰';
      mobileMenuBtn.setAttribute('aria-expanded', isOpen);
   });

   // Close menu when clicking on links
   navLinks.forEach(link => {
      link.addEventListener('click', function () {
         mobileMenu.classList.remove('active');
         mobileMenuBtn.textContent = '☰';
         mobileMenuBtn.setAttribute('aria-expanded', 'false');
      });
   });

   // Close menu when clicking outside
   document.addEventListener('click', function (e) {
      if (!mobileMenuBtn.contains(e.target) && !mobileMenu.contains(e.target)) {
         mobileMenu.classList.remove('active');
         mobileMenuBtn.textContent = '☰';
         mobileMenuBtn.setAttribute('aria-expanded', 'false');
      }
   });
}

// ===== CAROUSEL FUNCTIONALITY =====
function initCarousel() {
   const slides = document.querySelectorAll('.carousel-slide');
   const indicators = document.querySelectorAll('.carousel-indicator');
   const prevBtn = document.querySelector('.carousel-prev');
   const nextBtn = document.querySelector('.carousel-next');
   const carouselContainer = document.querySelector('.carousel-container');
   if (!slides.length || !carouselContainer || !prevBtn || !nextBtn) return;

   let currentSlide = 0;
   let isAutoPlaying = true;
   let autoPlayInterval;

   // Start auto-play
   function startAutoPlay() {
      if (isAutoPlaying) {
         autoPlayInterval = setInterval(() => {
            nextSlide();
         }, 5000);
      }
   }

   // Stop auto-play
   function stopAutoPlay() {
      clearInterval(autoPlayInterval);
   }

   // Go to specific slide
   function goToSlide(index) {
      // Remove active class from current slide and indicator
      slides[currentSlide].classList.remove('active');
      indicators[currentSlide]?.classList.remove('active');

      // Update current slide
      currentSlide = index;

      // Add active class to new slide and indicator
      slides[currentSlide].classList.add('active');
      indicators[currentSlide]?.classList.add('active');

   }

   // Next slide
   function nextSlide() {
      const next = (currentSlide + 1) % slides.length;
      goToSlide(next);
   }

   // Previous slide
   function prevSlide() {
      const prev = (currentSlide - 1 + slides.length) % slides.length;
      goToSlide(prev);
   }

   // Event listeners
   nextBtn.addEventListener('click', () => {
      nextSlide();
      stopAutoPlay();
   });

   prevBtn.addEventListener('click', () => {
      prevSlide();
      stopAutoPlay();
   });

   // Indicator clicks
   indicators.forEach((indicator, index) => {
      indicator.addEventListener('click', () => {
         goToSlide(index);
         stopAutoPlay();
      });
   });

   // Pause on hover, resume on leave
   carouselContainer.addEventListener('mouseenter', () => {
      isAutoPlaying = false;
      stopAutoPlay();
   });

   carouselContainer.addEventListener('mouseleave', () => {
      isAutoPlaying = true;
      startAutoPlay();
   });

   // Keyboard navigation
   document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
         prevSlide();
         stopAutoPlay();
      } else if (e.key === 'ArrowRight') {
         nextSlide();
         stopAutoPlay();
      }
   });

   // Touch/swipe support for mobile
   let touchStartX = 0;
   let touchEndX = 0;

   carouselContainer.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
   });

   carouselContainer.addEventListener('touchend', (e) => {
      touchEndX = e.changedTouches[0].screenX;
      handleSwipe();
   });

   function handleSwipe() {
      const swipeThreshold = 50;
      const diff = touchStartX - touchEndX;

      if (Math.abs(diff) > swipeThreshold) {
         if (diff > 0) {
            nextSlide(); // Swipe left - next slide
         } else {
            prevSlide(); // Swipe right - previous slide
         }
         stopAutoPlay();
      }
   }

   // Start the carousel
   startAutoPlay();
}

// ===== SMOOTH SCROLL =====
function initSmoothScroll() {
   // Smooth scroll for anchor links
   document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
         e.preventDefault();
         const target = document.querySelector(this.getAttribute('href'));

         if (target) {
            const offsetTop = target.offsetTop - 80; // Account for fixed navbar
            window.scrollTo({
               top: offsetTop,
               behavior: 'smooth'
            });
         }
      });
   });
}

// ===== SIGNUP FORM =====
function initSignupForm() {
   const form = document.getElementById('signup-form');
   if (!form) return; // ← impede erro se o form não existir
   const successMessage = document.getElementById('success-message');
   const nameInput = document.getElementById('name');
   const emailInput = document.getElementById('email');
   const nameError = document.getElementById('name-error');
   const emailError = document.getElementById('email-error');

   // Form validation
   function validateForm() {
      let isValid = true;

      // Clear previous errors
      nameError.textContent = '';
      emailError.textContent = '';
      nameInput.classList.remove('error');
      emailInput.classList.remove('error');

      // Validate name
      if (!nameInput.value.trim()) {
         nameError.textContent = 'Nome é obrigatório';
         nameInput.classList.add('error');
         isValid = false;
      }

      // Validate email
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailInput.value.trim()) {
         emailError.textContent = 'E-mail é obrigatório';
         emailInput.classList.add('error');
         isValid = false;
      } else if (!emailRegex.test(emailInput.value)) {
         emailError.textContent = 'E-mail inválido';
         emailInput.classList.add('error');
         isValid = false;
      }

      return isValid;
   }

   // Clear errors on input
   nameInput.addEventListener('input', () => {
      if (nameInput.classList.contains('error')) {
         nameError.textContent = '';
         nameInput.classList.remove('error');
      }
   });

   emailInput.addEventListener('input', () => {
      if (emailInput.classList.contains('error')) {
         emailError.textContent = '';
         emailInput.classList.remove('error');
      }
   });

   // Form submission
   form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (validateForm()) {
         // Hide form and show success message
         form.style.display = 'none';
         successMessage.classList.add('active');

         // Reset form after 3 seconds
         setTimeout(() => {
            form.style.display = 'block';
            successMessage.classList.remove('active');
            form.reset();
         }, 3000);
      }
   });
}

// ===== INTERSECTION OBSERVER FOR ANIMATIONS =====
function initIntersectionObserver() {
   // Animate elements when they come into view
   const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
   };

   const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
         if (entry.isIntersecting) {
            entry.target.style.animationPlayState = 'running';
            entry.target.classList.add('animate');
         }
      });
   }, observerOptions);

   // Observe elements with animation classes
   const animatedElements = document.querySelectorAll([
      '.hub-content',
      '.hub-image',
      '.signup-header',
      '.signup-form-container',
      '.partners-header',
      '.partner-card',
      '.partners-cta'
   ].join(','));

   animatedElements.forEach(el => {
      el.style.animationPlayState = 'paused';
      observer.observe(el);
   });
}

// ===== UTILITY FUNCTIONS =====

// Debounce function for performance
function debounce(func, wait) {
   let timeout;
   return function executedFunction(...args) {
      const later = () => {
         clearTimeout(timeout);
         func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
   };
}

// Throttle function for scroll events
function throttle(func, limit) {
   let inThrottle;
   return function () {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
         func.apply(context, args);
         inThrottle = true;
         setTimeout(() => inThrottle = false, limit);
      }
   };
}

// Add scroll-based navbar background
window.addEventListener('scroll', throttle(() => {
   const navbar = document.getElementById('navbar');
   if (!navbar || navbar.dataset.tema === 'canastra') return;
   if (window.scrollY > 100) {
      navbar.style.background = 'rgba(255, 255, 255, 0.98)';
      navbar.style.borderBottom = '1px solid hsl(214, 32%, 91%)';
   } else {
      navbar.style.background = 'rgba(255, 255, 255, 0.95)';
      navbar.style.borderBottom = '1px solid hsl(214, 32%, 91%)';
   }
}, 10));

// Performance: Lazy loading for images
function initLazyLoading() {
   const images = document.querySelectorAll('img[data-src]');

   const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
         if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            img.classList.remove('lazy');
            imageObserver.unobserve(img);
         }
      });
   });

   images.forEach(img => imageObserver.observe(img));
}

// Error handling for images
document.addEventListener('error', (e) => {
   if (e.target.tagName === 'IMG') {
      e.target.src = 'https://via.placeholder.com/800x400/22c55e/ffffff?text=Hub+Canastra';
      console.warn('Image failed to load:', e.target.src);
   }
}, true);

// Console welcome message
console.log('%c🌱 Hub Canastra', 'color: #22c55e; font-size: 20px; font-weight: bold;');
console.log('%cConectando o Agronegócio Sustentável', 'color: #666; font-size: 12px;');

// Analytics placeholder (replace with actual analytics code)
function trackEvent(eventName, properties = {}) {
   console.log('📊 Event:', eventName, properties);
   // Replace with your analytics service (Google Analytics, Mixpanel, etc.)
}

// Track user interactions
document.addEventListener('click', (e) => {
   if (e.target.matches('.btn')) {
      trackEvent('button_click', {
         button_text: e.target.textContent.trim(),
         button_class: e.target.className
      });
   }
});

// Export functions for external use (if needed)
window.HubCanastra = {
   trackEvent,
   debounce,
   throttle
};
