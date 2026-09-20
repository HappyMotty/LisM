/*
 * LisM 用の慣性スクロール Input Processor。
 * (roBaリポジトリで実装したものと同一のロジック)
 *
 * トラックボールを弾くようにスクロール操作した後、指を止めても
 * しばらく減速しながらスクロールが続く(いわゆる慣性スクロール)を実現する。
 *
 * 通常のInput Processorと違い、これは「入力が止まった後も自分で
 * タイマーを使って追加のスクロールイベントを生成し続ける」能動的な処理を行う。
 *
 * 動作の流れ:
 *  1. 対象コード(ホイール/水平ホイール)のイベントが来るたびに、
 *     速度・発生元デバイスを記憶し、TICK_MS後に減衰処理を予約する。
 *  2. TICK_MS間隔で新しいイベントが来続ける間は、予約が押し戻され続ける
 *     (=ユーザーが実際にスクロール操作中)。
 *  3. 入力が止まってTICK_MSが経過すると減衰処理が発火する。
 *     直前の速度がSTART_THRESHOLD未満なら、そのまま何もしない(通常の
 *     ゆっくりしたスクロールがただ止まっただけ、とみなす)。
 *  4. START_THRESHOLD以上だった場合のみ「慣性モード」に入り、
 *     DECAY_PERCENT%ずつ速度を減衰させながら合成イベントを注入し、
 *     MIN_VELOCITY未満になったら停止する。
 *
 * DECAY_PERCENTは1〜99に制限されているため、整数演算でも有限回で
 * 必ず0に収束する(無限にスクロールし続けることはない)。
 */
#define DT_DRV_COMPAT zmk_input_processor_scroll_inertia

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/input/input.h>
#include <drivers/input_processor.h>

#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

struct inertia_config {
    uint8_t type;
    size_t codes_len;
    uint16_t codes[];
};

struct inertia_data {
    const struct device *source_dev;
    uint16_t code;
    int32_t velocity;
    bool momentum_active;
    struct k_work_delayable decay_work;
};

static inline int32_t abs32(int32_t v) {
    return v < 0 ? -v : v;
}

static void decay_work_handler(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct inertia_data *data = CONTAINER_OF(dwork, struct inertia_data, decay_work);

    if (data->source_dev == NULL) {
        return;
    }

    if (!data->momentum_active) {
        if (abs32(data->velocity) < CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_START_THRESHOLD) {
            return; /* 通常のスクロールが止まっただけ。慣性はつけない */
        }
        data->momentum_active = true;
    }

    data->velocity =
        data->velocity * CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_DECAY_PERCENT / 100;

    if (abs32(data->velocity) < CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_MIN_VELOCITY) {
        data->momentum_active = false;
        return;
    }

    input_report_rel(data->source_dev, data->code, data->velocity, true, K_NO_WAIT);
    k_work_reschedule(&data->decay_work,
                       K_MSEC(CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_TICK_MS));
}

static int inertia_handle_event(const struct device *dev, struct input_event *event,
                                 uint32_t param1, uint32_t param2,
                                 struct zmk_input_processor_state *state) {
    if (!IS_ENABLED(CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_ENABLED)) {
        return ZMK_INPUT_PROC_CONTINUE;
    }

    const struct inertia_config *cfg = dev->config;
    struct inertia_data *data = dev->data;

    if (event->type != cfg->type) {
        return ZMK_INPUT_PROC_CONTINUE;
    }

    bool matched = false;
    for (int i = 0; i < cfg->codes_len; i++) {
        if (cfg->codes[i] == event->code) {
            matched = true;
            break;
        }
    }
    if (!matched) {
        return ZMK_INPUT_PROC_CONTINUE;
    }

    data->source_dev = event->dev;
    data->code = event->code;
    data->velocity = event->value;
    k_work_reschedule(&data->decay_work,
                       K_MSEC(CONFIG_ZMK_INPUT_PROCESSOR_SCROLL_INERTIA_TICK_MS));

    return ZMK_INPUT_PROC_CONTINUE;
}

static struct zmk_input_processor_driver_api inertia_driver_api = {
    .handle_event = inertia_handle_event,
};

static int inertia_init(const struct device *dev) {
    struct inertia_data *data = dev->data;
    k_work_init_delayable(&data->decay_work, decay_work_handler);
    return 0;
}

#define INERTIA_INST(n)                                                                          \
    static const struct inertia_config inertia_config_##n = {                                    \
        .type = DT_INST_PROP_OR(n, type, INPUT_EV_REL),                                          \
        .codes_len = DT_INST_PROP_LEN(n, codes),                                                 \
        .codes = DT_INST_PROP(n, codes),                                                         \
    };                                                                                           \
    static struct inertia_data inertia_data_##n;                                                 \
    DEVICE_DT_INST_DEFINE(n, inertia_init, NULL, &inertia_data_##n, &inertia_config_##n,          \
                           POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,                      \
                           &inertia_driver_api);

DT_INST_FOREACH_STATUS_OKAY(INERTIA_INST)
