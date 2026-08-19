/** Rendered once behind the whole app: masked grid, two slow brand glows
 *  (cyan + GoodBed navy) and a film grain. GPU-cheap, reduced-motion aware. */
export function AppBackground() {
  return (
    <div className="dr-bg" aria-hidden>
      <div className="dr-bg__grid" />
      <div className="dr-bg__glow dr-bg__glow--a" />
      <div className="dr-bg__glow dr-bg__glow--b" />
      <div className="dr-bg__grain" />
    </div>
  );
}
