"""The printed label has to survive a press and a warehouse phone camera.

These pin the two properties that were making tags hard to scan, both of which
are invisible in code review and only show up on paper:

  * the symbol must stay a 21x21 version 1, so each module is as wide as the
    label can afford;
  * it must keep FOUR modules of blank margin on every side, which the old
    label did not have — it printed a denser symbol AND crowded it.

They are geometry assertions rather than a rendering diff on purpose: a golden
PDF would fail on every harmless copy change and teach everyone to re-bless it.
"""

import qrcode

from app.services import qr as qr_svc


def test_a_token_is_short_uppercase_and_unambiguous():
    token = qr_svc.new_token()

    assert len(token) == qr_svc.TOKEN_LENGTH == 16
    assert token.isupper() or token.isdigit()
    # I, L, O and U are excluded so a human reading a scuffed label never has to
    # choose between 0 and O, or 1 and I and L.
    assert not (set(token) & set("ILOU"))
    assert set(token) <= set(qr_svc._TOKEN_ALPHABET)


def test_tokens_do_not_repeat():
    assert len({qr_svc.new_token() for _ in range(2000)}) == 2000


def test_the_symbol_stays_a_version_1_21x21():
    """17 characters would push it to 25x25 and shrink every module."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, border=0)
    qr.add_data(qr_svc.new_token())
    qr.make(fit=True)

    assert qr.version == 1
    assert qr.modules_count == qr_svc.QR_MODULES == 21


def test_the_label_leaves_a_full_four_module_quiet_zone():
    """The property the old label broke: the margin a decoder needs to find it."""
    module = qr_svc.QR_SIZE / qr_svc.QR_MODULES

    assert 4 * module <= qr_svc.QR_QUIET


def test_the_code_and_its_quiet_zone_fit_inside_box_b():
    """Quiet zone, symbol, quiet zone and the printed token, inside 41mm."""
    token_line = 3.5 * (qr_svc.mm)
    needed = qr_svc.QR_QUIET + qr_svc.QR_SIZE + qr_svc.QR_QUIET + token_line

    assert needed <= qr_svc.BOX_B_H, (
        f"Box B is {qr_svc.BOX_B_H / qr_svc.mm:.1f}mm and this needs "
        f"{needed / qr_svc.mm:.1f}mm — shrink QR_SIZE rather than the quiet zone."
    )


def test_modules_are_wider_than_the_old_label_printed_them():
    """The whole point: more ink per module than the 29x29 at 31mm it replaces."""
    old_module = (31 * qr_svc.mm) / 29
    new_module = qr_svc.QR_SIZE / qr_svc.QR_MODULES

    assert new_module > old_module
