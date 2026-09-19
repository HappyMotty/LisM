zephyr_library()

zephyr_library_sources_ifdef(CONFIG_INPUT src/input_processor_accel.c)
