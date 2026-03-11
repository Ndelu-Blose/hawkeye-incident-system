// Alertweb Solutions / HawkEye public UX enhancements
// - Sticky navbar state on scroll
// - Back-to-top button with smooth scroll

(function () {
  var header = document.querySelector(".hawkeye-public-header");
  var backToTop = document.querySelector(".hawkeye-back-to-top");

  if (!header && !backToTop) {
    return;
  }

  var lastKnownScrollY = 0;
  var ticking = false;
  var SHOW_THRESHOLD = 350;

  function onScroll() {
    lastKnownScrollY = window.scrollY || window.pageYOffset || 0;
    if (!ticking) {
      window.requestAnimationFrame(applyScrollEffects);
      ticking = true;
    }
  }

  function applyScrollEffects() {
    ticking = false;
    var y = lastKnownScrollY;

    if (header) {
      if (y > 16) {
        header.classList.add("hawkeye-public-header--scrolled");
      } else {
        header.classList.remove("hawkeye-public-header--scrolled");
      }
    }

    if (backToTop) {
      if (y > SHOW_THRESHOLD) {
        backToTop.classList.add("is-visible");
      } else {
        backToTop.classList.remove("is-visible");
      }
    }
  }

  if (backToTop) {
    backToTop.addEventListener("click", function (e) {
      e.preventDefault();
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  applyScrollEffects();
})();
