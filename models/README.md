# Bundled Piper voice models

The Arabic, Sinhala, and Tamil ONNX models in this directory provide local reply playback. Model
weights are stored with Git LFS; install Git LFS and run `git lfs pull` after cloning so the files
are real ONNX binaries rather than pointer files. Keep each `.onnx.json` configuration beside its
matching `.onnx` file and preserve the filenames because the application uses these fixed paths.

The application verifies each file's SHA-256 digest before loading it. The expected files are:

| File | SHA-256 | Source revision | License |
| --- | --- | --- | --- |
| `arabic/ar_JO-kareem-medium.onnx` | `9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e` | [Rhasspy Arabic model at v1.0.0](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/ar/ar_JO/kareem/medium) | MIT repository metadata; dataset license says "See URL" |
| `arabic/ar_JO-kareem-medium.onnx.json` | `ea6d9b9d9076dbdb6bf5c98c6a141ef154959d2359709b37855727964e7d6c4d` | [Rhasspy Arabic model at v1.0.0](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/ar/ar_JO/kareem/medium) | MIT repository metadata; dataset license says "See URL" |
| `sinhala/si_LK-ashoka-medium.onnx` | `7ad3e2fae1c8abbb389abb2cc7b17624b620082193e88407791ae68b9011a166` | [UNICEF Sinhala model revision](https://huggingface.co/unicef/piper-si_LK-ashoka-medium/commit/58c9ccaece6c9e54d275df1d922945d025fa2033) | MIT |
| `sinhala/si_LK-ashoka-medium.onnx.json` | `ff7910b0816934384fe5d7342b64a84596837fba513547062dada08844b2c184` | [UNICEF Sinhala model revision](https://huggingface.co/unicef/piper-si_LK-ashoka-medium/commit/58c9ccaece6c9e54d275df1d922945d025fa2033) | MIT |
| `tamil/ta_IN-rasa_female-medium.onnx` | `1befd7c4034429cecf3143d5eab4810b29833420aedb951bef4092779d074d59` | [TiniSoft Tamil model revision](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/commit/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496) | CC BY 4.0 |
| `tamil/ta_IN-rasa_female-medium.onnx.json` | `e49a5f947bfe64bc232d9f900a163b3b771b812780fd8efe0d411a3d8f4b4ee2` | [TiniSoft Tamil model revision](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/commit/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496) | CC BY 4.0 |

The application maps its Arabic (`ar-SA`) locale to the Jordanian (`ar_JO`) Kareem model. Regional
accent and pronunciation may therefore differ. The model card identifies a 22,050 Hz model,
links to the [Arabic training-data repository](https://github.com/AliMokhammad/arabicttstrain/),
and says the model was fine-tuned from the medium U.S. English Lessac voice. Its dataset-license
field says "See URL"; the linked repository does not state a license on its main page. The local
files also match the upstream `voices.json` MD5 values: `c0697df8a7fb180079cc5ac523f91a8e`
for the ONNX file and `dd70b31eb5a395907241b1e5367ace3a` for its JSON configuration.

The Tamil voice was trained on the female speaker from the
[AI4Bharat Rasa expressive speech dataset](https://huggingface.co/datasets/ai4bharat/Rasa).
It is an Indian Tamil (`ta-IN`) model used for the demo's Tamil (`ta-LK`) locale, so its accent can
differ from Sri Lankan Tamil. Test it with the intended audience and device.
Preserve its CC BY 4.0 license and attribution when redistributing it. Full attribution and
runtime-license links are in [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

To verify the checked-out files manually on PowerShell:

```powershell
Get-FileHash models/arabic/ar_JO-kareem-medium.onnx -Algorithm SHA256
Get-FileHash models/arabic/ar_JO-kareem-medium.onnx.json -Algorithm SHA256
Get-FileHash models/sinhala/si_LK-ashoka-medium.onnx -Algorithm SHA256
Get-FileHash models/sinhala/si_LK-ashoka-medium.onnx.json -Algorithm SHA256
Get-FileHash models/tamil/ta_IN-rasa_female-medium.onnx -Algorithm SHA256
Get-FileHash models/tamil/ta_IN-rasa_female-medium.onnx.json -Algorithm SHA256
```
