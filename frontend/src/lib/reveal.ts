// Svelte action: adds .in when the element scrolls into view. Stagger via the `delay` param (ms).
export function reveal(node: HTMLElement, delay = 0) {
	node.setAttribute('data-reveal', '');
	node.style.transitionDelay = `${delay}ms`;
	const show = () => { node.classList.add('in'); io.disconnect(); };
	const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) show(); }, { threshold: 0.1, rootMargin: '0px 0px -5% 0px' });
	io.observe(node);
	// ponytail: safety net — never leave content invisible if the observer misbehaves (print, odd embeds)
	const t = setTimeout(() => { if (node.getBoundingClientRect().top < innerHeight) show(); }, 1500);
	return { destroy: () => { io.disconnect(); clearTimeout(t); } };
}
