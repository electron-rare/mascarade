# Dataset refresh brief: iot

- generated_at: `2026-03-09T11:15:11`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/iot_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `5795`
- quality_status: `warning`
- ids_fixed_in_memory: `6005`
- duplicates_removed_during_refresh: `210`
- research_valid: `True`
- web_roots_count: `22`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [ESP-IDF programming guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/)
- [Home Assistant developer docs](https://developers.home-assistant.io/)

## Hugging Face sources
- [gouthamsk/esp_idf_code](https://huggingface.co/datasets/gouthamsk/esp_idf_code)
- [acon96/Home-Assistant-Requests](https://huggingface.co/datasets/acon96/Home-Assistant-Requests)
- [gavmac00/arduino-docs](https://huggingface.co/datasets/gavmac00/arduino-docs)
- [bshada/arduino.stackexchange.com](https://huggingface.co/datasets/bshada/arduino.stackexchange.com)

## Official GitHub sources
- [esp-idf](https://github.com/espressif/esp-idf)
- [espressif org](https://github.com/espressif)
- [home-assistant core](https://github.com/home-assistant/core)

## Software source roots
- [ESP-IDF product page](https://www.espressif.com/en/products/sdks/esp-idf)
- [Home Assistant developer portal](https://developers.home-assistant.io/)

## Specialized forums
- [ST Community](https://community.st.com/)
- [PlatformIO Community](https://community.platformio.org/)
- [ChibiOS Forum](https://forum.chibios.org/)
- [FreeRTOS Forums](https://forums.freertos.org/)
- [ARM Community Forums](https://community.arm.com/support-forums/)
- [Arduino Forum](https://forum.arduino.cc/)
- [EmbeddedRelated Forum](https://www.embeddedrelated.com/forum.php)
- [Electronics StackExchange STM32](https://electronics.stackexchange.com/questions/tagged/stm32)
- [Electronics StackExchange Embedded](https://electronics.stackexchange.com/questions/tagged/embedded)
- [All About Circuits Embedded Systems](https://forum.allaboutcircuits.com/forums/embedded-systems-and-microcontrollers.13/)

## Datasheet and vendor roots
- [ESP32 hardware reference](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/index.html)

## Search queries
- `site:docs.espressif.com esp-idf mqtt ota deep sleep`
- `site:developers.home-assistant.io integration websocket mqtt`
- `site:huggingface.co/datasets esp idf code dataset`

## Trusted domains
- `docs.espressif.com`
- `developers.home-assistant.io`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `13/18`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
