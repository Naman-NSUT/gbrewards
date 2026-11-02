import { describe, expect, it } from 'vitest';

import { __testing } from './banners';

const { toFormData } = __testing;

/**
 * Banner uploads are multipart, so every value crosses as text. These pin the
 * conversion, because the failure mode is not a type error — it is a string that
 * looks like data.
 */
describe('toFormData', () => {
  it('carries the fields that were filled in', () => {
    const image = new File(['x'], 'banner.jpg', { type: 'image/jpeg' });

    const fd = toFormData({ image, caption: 'Happy Diwali', sort_order: 1, is_active: true });

    expect(fd.get('caption')).toBe('Happy Diwali');
    expect(fd.get('sort_order')).toBe('1');
    expect(fd.get('is_active')).toBe('true');
    expect(fd.get('image')).toBe(image);
  });

  it('omits a cleared number instead of sending the word "null"', () => {
    // antd's InputNumber hands back null for a cleared field. String(null) is
    // "null", which the server cannot read as an integer — this was a 422 on
    // save with no indication of which field was at fault.
    const fd = toFormData({
      image: new File(['x'], 'b.jpg'),
      sort_order: null as unknown as number,
    });

    expect(fd.has('sort_order')).toBe(false);
  });

  it('omits a cleared caption rather than saving the text "null"', () => {
    // The quieter half of the same bug: no error, just a banner captioned "null".
    const fd = toFormData({
      image: new File(['x'], 'b.jpg'),
      caption: null as unknown as string,
      link_url: null as unknown as string,
    });

    expect(fd.has('caption')).toBe(false);
    expect(fd.has('link_url')).toBe(false);
  });

  it('omits a cleared switch rather than sending "null" for a boolean', () => {
    const fd = toFormData({
      image: new File(['x'], 'b.jpg'),
      is_active: null as unknown as boolean,
    });

    expect(fd.has('is_active')).toBe(false);
  });

  it('keeps an explicit false, which is a real choice and not an absence', () => {
    const fd = toFormData({ image: new File(['x'], 'b.jpg'), is_active: false });

    expect(fd.get('is_active')).toBe('false');
  });

  it('keeps zero, which is the first sort position and not an absence', () => {
    const fd = toFormData({ image: new File(['x'], 'b.jpg'), sort_order: 0 });

    expect(fd.get('sort_order')).toBe('0');
  });

  it('keeps an empty caption, which is how a caption gets cleared on edit', () => {
    const fd = toFormData({ caption: '' });

    expect(fd.get('caption')).toBe('');
  });

  it('sends no image on a PATCH that only renames', () => {
    // The backend keeps the existing image when the field is absent.
    const fd = toFormData({ caption: 'New caption' });

    expect(fd.has('image')).toBe(false);
  });
});
