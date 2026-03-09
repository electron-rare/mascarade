# Dataset refresh brief: stm32

- generated_at: `2026-03-09T09:42:22`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/stm32_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `594`
- quality_status: `warning`
- ids_fixed_in_memory: `2012`
- duplicates_removed_during_refresh: `1418`
- research_valid: `True`
- web_roots_count: `21`
- forum_count: `10`
- quality_score: `8`

## Web research roots
- [ST STM32Cube docs](https://dev.st.com/stm32cube-docs/)
- [ST Community](https://community.st.com/)

## Hugging Face sources
- [MuratKomurcu/stm32-hal-dataset](https://huggingface.co/datasets/MuratKomurcu/stm32-hal-dataset)

## Official GitHub sources
- [STMicroelectronics org](https://github.com/STMicroelectronics)
- [STM32CubeF4](https://github.com/STMicroelectronics/STM32CubeF4)
- [STM32CubeH7](https://github.com/STMicroelectronics/STM32CubeH7)
- [STM32CubeG4](https://github.com/STMicroelectronics/STM32CubeG4)

## Software source roots
- [STM32Cube firmware hub](https://github.com/STMicroelectronics)
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
- [STM32 mainstream MCU documentation hub](https://www.st.com/en/microcontrollers-microprocessors/stm32-mainstream-mcus/documentation.html)
- [STM32 family documentation portal](https://www.st.com/en/microcontrollers-microprocessors.html)

## Search queries
- `site:dev.st.com stm32 dma uart application note`
- `site:community.st.com stm32 freertos low power`
- `site:huggingface.co/datasets stm32 hal dataset`

## Trusted domains
- `dev.st.com`
- `community.st.com`
- `huggingface.co`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
