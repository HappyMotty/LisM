add_subdirectory(drivers)

# ZMK app自身のinclude/ (drivers/input_processor.h 等) はPRIVATEスコープのため、
# out-of-treeモジュールから見えるようにグローバルに追加する
zephyr_include_directories(${APPLICATION_SOURCE_DIR}/include)
