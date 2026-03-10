# Dataset refresh brief: embedded

- generated_at: `2026-03-09T12:09:19`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/embedded_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `7014`
- quality_status: `warning`
- ids_fixed_in_memory: `8344`
- duplicates_removed_during_refresh: `1330`
- research_valid: `True`
- web_roots_count: `21`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [ESP-IDF programming guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/)
- [ST STM32Cube docs](https://dev.st.com/stm32cube-docs/)

## Hugging Face sources
- [gouthamsk/esp_idf_code](https://huggingface.co/datasets/gouthamsk/esp_idf_code)
- [gavmac00/arduino-docs](https://huggingface.co/datasets/gavmac00/arduino-docs)
- [bshada/arduino.stackexchange.com](https://huggingface.co/datasets/bshada/arduino.stackexchange.com)

## Official GitHub sources
- [esp-idf](https://github.com/espressif/esp-idf)
- [STMicroelectronics org](https://github.com/STMicroelectronics)

## Software source roots
- [ESP-IDF product page](https://www.espressif.com/en/products/sdks/esp-idf)
- [STM32Cube docs](https://dev.st.com/stm32cube-docs/)

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
- [STM32 MCU documentation](https://www.st.com/en/microcontrollers-microprocessors/stm32-mainstream-mcus/documentation.html)

## Search queries
- `site:docs.espressif.com esp-idf spi dma cache alignment`
- `site:dev.st.com cortex-m startup linker script dma application note`
- `site:huggingface.co/datasets embedded firmware dataset`

## Trusted domains
- `docs.espressif.com`
- `dev.st.com`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `12/18`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
