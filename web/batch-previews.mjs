class BatchPreviews extends HTMLElement {
  connectedCallback() {
    const track = this.querySelector('.preview-track'), controls = this.querySelector('.preview-controls');
    if (!track || !controls) return;
    this.events = new AbortController();
    const options = {signal:this.events.signal};
    const [previous, next] = controls.querySelectorAll('button');
    const cards = [...track.querySelectorAll('a')];
    const sync = () => {
      const end = track.scrollWidth - track.clientWidth;
      controls.hidden = end <= 2;
      previous.disabled = track.scrollLeft < 2;
      next.disabled = track.scrollLeft >= end - 2;
    };
    const scroll = card => {
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
      track.scrollTo({left:card.parentElement.offsetLeft, behavior:reduce ? 'instant' : 'smooth'});
    };
    controls.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button || button.disabled) return;
      const card = button === next ? cards.find(card => card.parentElement.offsetLeft > track.scrollLeft + 2)
        : cards.findLast(card => card.parentElement.offsetLeft < track.scrollLeft - 2);
      if (card) scroll(card);
    }, options);
    track.addEventListener('keydown', event => {
      const index = cards.indexOf(event.target);
      if (index < 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = {ArrowLeft:index - 1, ArrowRight:index + 1, Home:0, End:cards.length - 1}[event.key];
      if (target === undefined) return;
      event.preventDefault();
      if (!cards[target]) return;
      cards[target].focus({preventScroll:true});
      scroll(cards[target]);
    }, options);
    track.addEventListener('scroll', sync, {...options, passive:true});
    this.resize = new ResizeObserver(sync);
    this.resize.observe(track);
    sync();
  }
  disconnectedCallback() {
    this.events?.abort();
    this.resize?.disconnect();
  }
}
customElements.define('batch-previews', BatchPreviews);
