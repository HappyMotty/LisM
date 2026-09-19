/*
 * LisM 用の速度感応型ポインタ加速 Input Processor。
 * (roBaリポジトリで実装したものと同一のロジック)
 *
 * トラックボールの1レポートあたりの移動量(絶対値)に応じて、
 * CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MIN 〜 SPEED_MAX の範囲で
 * MIN_FACTOR(%) 〜 MAX_FACTOR(%) の倍率を線形補間して適用する。
 */
#define DT_DRV_COMPAT zmk_input_processor_accel

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <drivers/input_processor.h>

#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

struct accel_config {
    uint8_t type;
    size_t codes_len;
    uint16_t codes[];
};

static int16_t apply_accel(int16_t value) {
    int32_t magnitude = value < 0 ? -(int32_t)value : (int32_t)value;

    const int32_t min_factor = CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MIN_FACTOR;
    const int32_t max_factor = CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MAX_FACTOR;
    const int32_t speed_min = CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MIN;
    const int32_t speed_max = CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MAX;

    int32_t factor;
    if (speed_max <= speed_min || magnitude <= speed_min) {
        factor = min_factor;
    } else if (magnitude >= speed_max) {
        factor = max_factor;
    } else {
        factor = min_factor +
                 (max_factor - min_factor) * (magnitude - speed_min) / (speed_max - speed_min);
    }

    int32_t scaled = (int32_t)value * factor / 100;

    if (scaled > INT16_MAX) {
        scaled = INT16_MAX;
    } else if (scaled < INT16_MIN) {
        scaled = INT16_MIN;
    }

    return (int16_t)scaled;
}

static int accel_handle_event(const struct device *dev, struct input_event *event,
                               uint32_t param1, uint32_t param2,
                               struct zmk_input_processor_state *state) {
    const struct accel_config *cfg = dev->config;

    if (event->type != cfg->type) {
        return ZMK_INPUT_PROC_CONTINUE;
    }

    for (int i = 0; i < cfg->codes_len; i++) {
        if (cfg->codes[i] == event->code) {
            int16_t before = event->value;
            event->value = apply_accel(event->value);
            LOG_DBG("accel: code=%d value=%d -> %d", event->code, before, event->value);
            break;
        }
    }

    return ZMK_INPUT_PROC_CONTINUE;
}

static struct zmk_input_processor_driver_api accel_driver_api = {
    .handle_event = accel_handle_event,
};

#define ACCEL_INST(n)                                                                             \
    static const struct accel_config accel_config_##n = {                                         \
        .type = DT_INST_PROP_OR(n, type, INPUT_EV_REL),                                            \
        .codes_len = DT_INST_PROP_LEN(n, codes),                                                   \
        .codes = DT_INST_PROP(n, codes),                                                           \
    };                                                                                             \
    DEVICE_DT_INST_DEFINE(n, NULL, NULL, NULL, &accel_config_##n, POST_KERNEL,                     \
                           CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &accel_driver_api);

DT_INST_FOREACH_STATUS_OKAY(ACCEL_INST)
