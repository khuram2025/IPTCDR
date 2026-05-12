// Landing Page JavaScript - Ultra Modern Interactions

document.addEventListener('DOMContentLoaded', function() {

    // Smooth scrolling for anchor links
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
        });
    });

    // Navbar scroll effect
    const navbar = document.querySelector('.navbar');
    let lastScrollY = window.scrollY;

    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;

        if (currentScrollY > 100) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 4px 6px -1px rgb(0 0 0 / 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = 'none';
        }

        // Hide/show navbar on scroll
        if (currentScrollY > lastScrollY && currentScrollY > 200) {
            navbar.style.transform = 'translateY(-100%)';
        } else {
            navbar.style.transform = 'translateY(0)';
        }

        lastScrollY = currentScrollY;
    });

    // Mobile menu toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            navToggle.querySelector('i').classList.toggle('fa-bars');
            navToggle.querySelector('i').classList.toggle('fa-times');
        });
    }

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe feature cards
    document.querySelectorAll('.feature-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });

    // Observe stat cards
    document.querySelectorAll('.stat-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateX(-30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });

    // Animate hero stats on load
    const heroStats = document.querySelectorAll('.stat-number');
    heroStats.forEach(stat => {
        const finalValue = stat.textContent;
        let currentValue = 0;
        const increment = finalValue.includes('%') ? 1 :
                         finalValue.includes('$') ? 100 :
                         finalValue.includes('+') ? 10 : 1;

        const timer = setInterval(() => {
            currentValue += increment;
            if (finalValue.includes('%')) {
                stat.textContent = currentValue + '%';
                if (currentValue >= parseFloat(finalValue)) {
                    stat.textContent = finalValue;
                    clearInterval(timer);
                }
            } else if (finalValue.includes('$')) {
                stat.textContent = '$' + currentValue.toLocaleString();
                if (currentValue >= parseInt(finalValue.replace(/[$,]/g, ''))) {
                    stat.textContent = finalValue;
                    clearInterval(timer);
                }
            } else if (finalValue.includes('+')) {
                stat.textContent = currentValue + '+';
                if (currentValue >= parseInt(finalValue.replace('+', ''))) {
                    stat.textContent = finalValue;
                    clearInterval(timer);
                }
            } else {
                stat.textContent = currentValue.toFixed(1);
                if (currentValue >= parseFloat(finalValue)) {
                    stat.textContent = finalValue;
                    clearInterval(timer);
                }
            }
        }, 50);
    });

    // Dashboard preview animation
    const dashboardPreview = document.querySelector('.dashboard-preview');
    if (dashboardPreview) {
        setTimeout(() => {
            dashboardPreview.style.transform = 'perspective(1000px) rotateY(-10deg)';
        }, 1000);
    }

    // Chart bars animation
    const chartBars = document.querySelectorAll('.chart-bar');
    chartBars.forEach((bar, index) => {
        setTimeout(() => {
            bar.style.animation = `chartGrow 1s ease-out ${index * 0.1}s both`;
        }, 2000);
    });

    // Parallax effect for hero background
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const parallaxElements = document.querySelectorAll('.bg-circle');

        parallaxElements.forEach((element, index) => {
            const speed = 0.5 + (index * 0.1);
            element.style.transform = `translateY(${scrolled * speed}px)`;
        });
    });

    // Button hover effects
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Add loading animation to page
    const pageLoader = document.createElement('div');
    pageLoader.className = 'page-loader';
    pageLoader.innerHTML = `
        <div class="loader-content">
            <div class="loader-spinner"></div>
            <div class="loader-text">Loading 3CX Billing Software...</div>
        </div>
    `;

    // Add loader styles
    const loaderStyles = `
        .page-loader {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: opacity 0.5s ease;
        }

        .loader-content {
            text-align: center;
            color: white;
        }

        .loader-spinner {
            width: 60px;
            height: 60px;
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }

        .loader-text {
            font-size: 1.125rem;
            font-weight: 500;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.textContent = loaderStyles;
    document.head.appendChild(styleSheet);

    // Show loader only on initial page load
    if (document.readyState === 'loading') {
        document.body.appendChild(pageLoader);

        window.addEventListener('load', () => {
            setTimeout(() => {
                pageLoader.style.opacity = '0';
                setTimeout(() => {
                    if (pageLoader.parentNode) {
                        pageLoader.parentNode.removeChild(pageLoader);
                    }
                }, 500);
            }, 1000);
        });
    }

    // Add typing effect to hero title
    const heroTitle = document.querySelector('.hero-title');
    if (heroTitle) {
        const originalText = heroTitle.innerHTML;
        heroTitle.innerHTML = '';

        let index = 0;
        const typingSpeed = 50;

        function typeWriter() {
            if (index < originalText.length) {
                heroTitle.innerHTML = originalText.substring(0, index + 1);
                index++;
                setTimeout(typeWriter, typingSpeed);
            }
        }

        setTimeout(typeWriter, 1500);
    }

    // Add click tracking for analytics
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function() {
            const buttonText = this.textContent.trim();
            console.log(`Button clicked: ${buttonText}`);

            // You can add Google Analytics or other tracking here
            if (typeof gtag !== 'undefined') {
                gtag('event', 'click', {
                    'event_category': 'Button',
                    'event_label': buttonText
                });
            }
        });
    });

    // Add form validation if contact forms are added later
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    // Preload critical images for better performance
    const criticalImages = [
        '/static/images/3cx-billing-og.jpg',
        '/static/images/3cx-billing-twitter.jpg'
    ];

    criticalImages.forEach(src => {
        const img = new Image();
        img.src = src;
    });

    // Add scroll progress indicator
    const progressBar = document.createElement('div');
    progressBar.className = 'scroll-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        z-index: 9999;
        transition: width 0.1s ease;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', () => {
        const scrollTop = window.pageYOffset;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressBar.style.width = scrollPercent + '%';
    });

    console.log('3CX Billing Landing Page loaded successfully!');
});