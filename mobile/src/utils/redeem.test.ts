import { clampQuantity, maxRedeemableQuantity, MAX_QUANTITY } from './redeem';

/**
 * The slider's range. What matters is that it never offers a quantity the server
 * will refuse — a worker who drags to 6 and gets "insufficient balance" has been
 * lied to by the UI.
 */
describe('maxRedeemableQuantity', () => {
  it('offers as many as the balance covers', () => {
    expect(maxRedeemableQuantity(300, 50)).toBe(6);
  });

  it('rounds down rather than offering a part-afforded one', () => {
    expect(maxRedeemableQuantity(290, 50)).toBe(5);
  });

  it('offers none when a single one is out of reach', () => {
    expect(maxRedeemableQuantity(40, 50)).toBe(0);
    expect(maxRedeemableQuantity(0, 50)).toBe(0);
  });

  it('does not divide by zero on a reward priced at nothing', () => {
    // Infinity here would render a slider with no end and submit a request the
    // server rejects outright.
    expect(maxRedeemableQuantity(300, 0)).toBe(0);
    expect(Number.isFinite(maxRedeemableQuantity(300, 0))).toBe(true);
  });

  it('never exceeds the ceiling the server enforces', () => {
    expect(maxRedeemableQuantity(10_000_000, 1)).toBe(MAX_QUANTITY);
  });
});

describe('clampQuantity', () => {
  it('holds a choice that is still affordable', () => {
    expect(clampQuantity(3, 6)).toBe(3);
  });

  it('pulls a stale choice down when the balance drops mid-screen', () => {
    // Points were spent elsewhere after the slider was dragged.
    expect(clampQuantity(6, 2)).toBe(2);
  });

  it('never goes below one', () => {
    expect(clampQuantity(0, 6)).toBe(1);
    expect(clampQuantity(-4, 6)).toBe(1);
  });

  it('stays at one when nothing is affordable, so the label reads sensibly', () => {
    expect(clampQuantity(3, 0)).toBe(1);
  });
});
