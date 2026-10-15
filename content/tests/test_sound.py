"""The sound design rules hold to their numbers (docs/content/SOUND_DESIGN.md)."""
import numpy as np

from hubricon_content import sound

SR = sound.SR


def test_a_breath_between_words_is_pulled_down_not_cut():
    vo = np.ones(SR * 2)
    out = sound.breath_gate(vo, [{"start": 0.0, "end": 0.5}, {"start": 1.2, "end": 1.8}])
    gap = out[int(0.7 * SR):int(1.0 * SR)]
    assert np.allclose(gap, 10 ** (sound.BREATH_DB / 20))      # down by BREATH_DB, never to silence
    assert out[int(0.2 * SR)] == 1.0 and out[int(1.5 * SR)] == 1.0


def test_the_music_loses_the_voice_band_under_speech_more_than_its_lows():
    t = np.arange(SR * 2) / SR
    low, mid = np.sin(2 * np.pi * 80 * t), np.sin(2 * np.pi * 1500 * t)
    speaking = np.ones(len(t))
    rms = lambda x: np.sqrt(np.mean(x[SR // 2:] ** 2))
    assert rms(sound.carve(mid, speaking)) / rms(mid) < 0.35            # about -12 dB
    assert rms(sound.carve(low, speaking)) / rms(low) > 0.5             # about -4 dB


def test_the_bed_dips_just_before_a_hero_figure_and_recovers():
    g = sound.predips(SR * 3, [1.0])
    assert g[int(0.5 * SR)] == 1.0
    assert abs(g[int(1.0 * SR) - 1] - 10 ** (sound.PREDIP_DB / 20)) < 0.01
    assert g[int(2.0 * SR)] == 1.0


def test_two_and_a_half_keeps_the_more_important_of_crowded_effects():
    out = sound.thin({"tick": [1.0], "paper": [1.1], "room": [5.0], "sub": [1.0], "riser": []})
    assert out["paper"] == []                       # crowded by a tick: the tick wins
    assert out["tick"] == [1.0] and out["sub"] == [1.0]   # a sub under a tick is one designed hit
    assert out["room"] == [5.0]


def test_no_two_instances_of_a_sound_are_identical():
    rng = np.random.default_rng(1)
    clip = np.sin(np.linspace(0, 40, 2000))
    a, ga = sound.vary(clip, rng)
    b, gb = sound.vary(clip, rng)
    assert len(a) != len(b) or ga != gb


def test_the_stereo_field_folds_back_to_the_mono_mix():
    rng = np.random.default_rng(3)
    mid = rng.normal(0, 0.1, SR).astype(np.float32)
    side = sound.widen(mid, sound.WIDTH_BED)
    left, right = mid + side, mid - side
    assert np.allclose((left + right) / 2, mid, atol=1e-6)        # mono: exactly the mono mix
    assert np.corrcoef(left, right)[0, 1] < 0.95                    # stereo: wider than mono


def test_the_side_level_is_measured_under_the_centre():
    mid = np.ones(1000, dtype=np.float32)
    assert sound.side_under_mid_db(mid, mid * 0.1) == 20.0
