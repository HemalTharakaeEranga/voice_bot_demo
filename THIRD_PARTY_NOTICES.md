# Third-party notices

This project includes or installs the components below. Their licenses apply to those components
independently of the project's MIT license.

## Piper text-to-speech runtime

- Package: `piper-tts==1.8.0`
- Project: [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)
- License: [GNU General Public License v3.0 or later](https://github.com/OHF-Voice/piper1-gpl/blob/main/COPYING)

## Sinhala voice model

- Model: `unicef/piper-si_LK-ashoka-medium`
- Publisher: UNICEF
- Source revision: [`58c9ccaece6c9e54d275df1d922945d025fa2033`](https://huggingface.co/unicef/piper-si_LK-ashoka-medium/commit/58c9ccaece6c9e54d275df1d922945d025fa2033)
- License: [MIT](https://opensource.org/license/mit)
- Included file SHA-256 values:
  - `si_LK-ashoka-medium.onnx`: `7ad3e2fae1c8abbb389abb2cc7b17624b620082193e88407791ae68b9011a166`
  - `si_LK-ashoka-medium.onnx.json`: `ff7910b0816934384fe5d7342b64a84596837fba513547062dada08844b2c184`

## Arabic voice model

- Model: `rhasspy/piper-voices` `ar_JO-kareem-medium`
- Publisher: Rhasspy
- Source revision: [Piper voices v1.0.0, Arabic/Jordan/Kareem/medium](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/ar/ar_JO/kareem/medium)
- Repository license metadata: [MIT](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0)
- Included file SHA-256 values:
  - `ar_JO-kareem-medium.onnx`: `9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e`
  - `ar_JO-kareem-medium.onnx.json`: `ea6d9b9d9076dbdb6bf5c98c6a141ef154959d2359709b37855727964e7d6c4d`

The voice-specific model card identifies the language as Jordanian Arabic (`ar_JO`), a 22,050 Hz
sample rate, and the [Arabic TTS training repository](https://github.com/AliMokhammad/arabicttstrain/)
as its dataset source. It records the dataset license as "See URL" and says the voice was
fine-tuned from the medium U.S. English Lessac voice. The linked dataset repository does not state
a license on its main page. Review its terms before redistributing the Arabic model. The
application maps this Jordanian voice to its Saudi Arabia locale (`ar-SA`), so regional accent and
pronunciation may differ.

## Tamil voice model

- Model: `tinisoft/piper-ta_IN-rasa_female-medium`
- Publisher: TiniSoft
- Source revision: [`89e15edafc8b31e66ddf25f2adbe3bd3f20a9496`](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/commit/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496)
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- Included file SHA-256 values:
  - `ta_IN-rasa_female-medium.onnx`: `1befd7c4034429cecf3143d5eab4810b29833420aedb951bef4092779d074d59`
  - `ta_IN-rasa_female-medium.onnx.json`: `e49a5f947bfe64bc232d9f900a163b3b771b812780fd8efe0d411a3d8f4b4ee2`

The Tamil voice was trained on the female speaker from the
[AI4Bharat Rasa expressive speech dataset](https://huggingface.co/datasets/ai4bharat/Rasa).
The model publisher requests citation of:

> Praveen Srinivasa Varadhan, Ashwin Sankar, Giri Raju, and Mitesh M. Khapra.
> "Rasa: Building Expressive Speech Synthesis Systems for Indian Languages in Low-resource
> Settings." Proceedings of INTERSPEECH, 2024.

The corresponding paper is available as [arXiv:2407.14056](https://arxiv.org/abs/2407.14056).
