/** Global Aceternity-style backdrop rendered once behind the whole app:
 *  animated grid masked by a top spotlight + slow-drifting violet glows +
 *  faint diagonal beams + film grain. GPU-friendly, reduced-motion aware. */
export function AppBackground() {
  return (
    <div className="sr-bg" aria-hidden>
      <div className="sr-bg__grid" />
      <div className="sr-bg__glow sr-bg__glow--a" />
      <div className="sr-bg__glow sr-bg__glow--b" />
      <div className="sr-bg__beams" />
      <div className="sr-bg__grain" />
    </div>
  );
}
