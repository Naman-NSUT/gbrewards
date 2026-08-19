import { Link } from 'react-router-dom';

interface RegisterCtaProps {
  /** Carried into the form so the customer does not retype what they just typed. */
  serial?: string;
}

/**
 * The whole reason this site is public.
 *
 * A lookup that finds nothing means a mattress was sold and the shop never
 * created the sale record — the exact failure the product exists to catch. So
 * this is not a polite "no results" line; it is the loudest thing on the screen,
 * and it goes straight to self-registration.
 */
export function RegisterCta({ serial }: RegisterCtaProps) {
  const to = serial ? `/register?serial=${encodeURIComponent(serial)}` : '/register';
  return (
    <section className="cta">
      <h2>Bought a GoodBed mattress but your warranty is not registered?</h2>
      <p>
        Register it now. Send us your purchase details and a photo of your bill, and GoodBed will
        add it to your name.
      </p>
      <Link className="btn" to={to}>
        Register my warranty
      </Link>
    </section>
  );
}
