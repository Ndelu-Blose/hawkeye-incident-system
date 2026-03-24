// Alertweb Solutions / HawkEye public UX enhancements
// - Sticky navbar state on scroll
// - Back-to-top button with smooth scroll

(function () {
  var header = document.querySelector(".hawkeye-public-header");
  var backToTop = document.querySelector(".hawkeye-back-to-top");
  var navLinks = Array.prototype.slice.call(document.querySelectorAll(".hawkeye-public-link[href]"));
  var sectionLinks = [];
  var pageLinks = [];

  if (!header && !backToTop && navLinks.length === 0) {
    return;
  }

  navLinks.forEach(function (link) {
    var rawHref = link.getAttribute("href");
    if (!rawHref || rawHref === "#") {
      return;
    }
    var href = new URL(rawHref, window.location.origin);
    var samePath = href.pathname === window.location.pathname;
    if (samePath && href.hash) {
      var target = document.querySelector(href.hash);
      if (target) {
        sectionLinks.push({ link: link, target: target, hash: href.hash });
      }
    } else if (!href.hash && href.pathname === window.location.pathname) {
      pageLinks.push(link);
    }
  });

  var lastKnownScrollY = 0;
  var ticking = false;
  var SHOW_THRESHOLD = 350;

  function clearActiveLinks() {
    navLinks.forEach(function (link) {
      link.classList.remove("is-active");
      link.removeAttribute("aria-current");
    });
  }

  function markActive(link) {
    if (!link) return;
    link.classList.add("is-active");
    link.setAttribute("aria-current", "page");
  }

  function syncActiveNav(y) {
    if (sectionLinks.length === 0 && pageLinks.length === 0) {
      return;
    }

    clearActiveLinks();

    if (sectionLinks.length > 0) {
      var selected = null;
      var probeY = y + 140;
      for (var i = 0; i < sectionLinks.length; i += 1) {
        var item = sectionLinks[i];
        if (item.target.offsetTop <= probeY) {
          selected = item;
        }
      }
      if (selected) {
        markActive(selected.link);
        return;
      }
    }

    if (pageLinks.length > 0) {
      markActive(pageLinks[0]);
    }
  }

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

    syncActiveNav(y);
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
  window.addEventListener("hashchange", function () {
    lastKnownScrollY = window.scrollY || window.pageYOffset || 0;
    syncActiveNav(lastKnownScrollY);
  });
  applyScrollEffects();
})();

(function () {
  var body = document.body;
  var backdrop = document.querySelector("[data-drawer-backdrop]");
  var toggles = Array.prototype.slice.call(document.querySelectorAll("[data-drawer-toggle]"));
  if (!body || toggles.length === 0) {
    return;
  }

  var activeDrawer = null;
  var lastTrigger = null;

  function focusableElements(node) {
    if (!node) return [];
    return Array.prototype.slice.call(
      node.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      ),
    );
  }

  function syncToggleState(drawer, expanded) {
    var id = drawer ? "#" + drawer.id : "";
    toggles.forEach(function (toggle) {
      if (toggle.getAttribute("data-drawer-target") === id) {
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      }
    });
  }

  function closeDrawer() {
    if (!activeDrawer) return;
    activeDrawer.classList.remove("is-open");
    activeDrawer.setAttribute("aria-hidden", "true");
    body.classList.remove("drawer-open");
    if (backdrop) {
      backdrop.classList.remove("is-open");
      backdrop.setAttribute("hidden", "hidden");
    }
    syncToggleState(activeDrawer, false);
    if (lastTrigger) {
      lastTrigger.focus();
    }
    activeDrawer = null;
  }

  function openDrawer(drawer, trigger) {
    if (!drawer) return;
    if (activeDrawer && activeDrawer !== drawer) {
      closeDrawer();
    }
    activeDrawer = drawer;
    lastTrigger = trigger || null;
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    body.classList.add("drawer-open");
    if (backdrop) {
      backdrop.removeAttribute("hidden");
      backdrop.classList.add("is-open");
    }
    syncToggleState(drawer, true);

    var targets = focusableElements(drawer);
    if (targets.length > 0) {
      targets[0].focus();
    } else {
      drawer.focus();
    }
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-drawer-toggle]");
    if (toggle) {
      var targetSelector = toggle.getAttribute("data-drawer-target");
      var drawer = targetSelector ? document.querySelector(targetSelector) : null;
      if (!drawer) return;
      if (activeDrawer && activeDrawer === drawer) {
        closeDrawer();
      } else {
        openDrawer(drawer, toggle);
      }
      return;
    }

    if (event.target.closest("[data-drawer-close]")) {
      closeDrawer();
      return;
    }

    if (activeDrawer && event.target.closest("[data-mobile-drawer] a[href]")) {
      closeDrawer();
      return;
    }

    if (event.target.closest("[data-drawer-backdrop]")) {
      closeDrawer();
      return;
    }

  });

  document.addEventListener("keydown", function (event) {
    if (!activeDrawer) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeDrawer();
      return;
    }

    if (event.key !== "Tab") return;

    var nodes = focusableElements(activeDrawer);
    if (nodes.length === 0) return;

    var first = nodes[0];
    var last = nodes[nodes.length - 1];
    var current = document.activeElement;

    if (event.shiftKey && current === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && current === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();
