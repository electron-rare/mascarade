# Dataset refresh brief: platformio

- generated_at: `2026-03-09T12:09:01`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/platformio_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `3386`
- quality_status: `warning`
- ids_fixed_in_memory: `3508`
- duplicates_removed_during_refresh: `122`
- research_valid: `True`
- web_roots_count: `23`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [PlatformIO docs](https://docs.platformio.org/)
- [ESP-IDF programming guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/)

## Hugging Face sources
- [gavmac00/arduino-docs](https://huggingface.co/datasets/gavmac00/arduino-docs)
- [gouthamsk/esp_idf_code](https://huggingface.co/datasets/gouthamsk/esp_idf_code)
- [bshada/arduino.stackexchange.com](https://huggingface.co/datasets/bshada/arduino.stackexchange.com)

## Official GitHub sources
- [platformio-core](https://github.com/platformio/platformio-core)
- [platformio docs](https://github.com/platformio/platformio-docs)
- [platform-espressif32](https://github.com/platformio/platform-espressif32)
- [esp-idf](https://github.com/espressif/esp-idf)

## Software source roots
- [PlatformIO org](https://github.com/platformio)
- [PlatformIO docs](https://docs.platformio.org/)
- [PlatformIO examples](https://github.com/platformio/platformio-examples)

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
- `site:docs.platformio.org monitor filters unit testing library_deps`
- `site:docs.espressif.com esp32 ota mqtt platformio`
- `site:huggingface.co/datasets arduino stackexchange dataset`

## Trusted domains
- `docs.platformio.org`
- `docs.espressif.com`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `15/20`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
