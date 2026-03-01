/**
 * 天气插件内联国际化消息
 *
 * 插件自带翻译，通过 setup() 注册到宿主 i18n。
 * 不依赖宿主 locale 文件。
 */

export const zhCN: Record<string, Record<string, string>> = {
  _meta: {
    lang: 'zh',
  },
  ui: {
    temperature: '温度',
    humidity: '湿度',
    wind_speed: '风速',
    uv_index: '紫外线',
    forecast: '未来预报',
    change_city: '切换城市',
    search_city: '搜索城市...',
    recent_cities: '最近城市',
    popular_cities: '热门城市',
    auto_locate: '自动定位',
    locating: '定位中...',
    loading: '加载天气中...',
    error: '天气数据获取失败',
    retry: '重试',
    today: '今天',
    tomorrow: '明天',
    day_after: '后天',
    weekday_0: '周日',
    weekday_1: '周一',
    weekday_2: '周二',
    weekday_3: '周三',
    weekday_4: '周四',
    weekday_5: '周五',
    weekday_6: '周六',
  },
  error: {
    city_not_found: '未找到该城市',
    api_timeout: '天气服务请求超时',
    network: '网络错误，请稍后重试',
  },
};

export const enUS: Record<string, Record<string, string>> = {
  _meta: {
    lang: 'en',
  },
  ui: {
    temperature: 'Temperature',
    humidity: 'Humidity',
    wind_speed: 'Wind Speed',
    uv_index: 'UV Index',
    forecast: 'Forecast',
    change_city: 'Change City',
    search_city: 'Search city...',
    recent_cities: 'Recent Cities',
    popular_cities: 'Popular Cities',
    auto_locate: 'Auto Locate',
    locating: 'Locating...',
    loading: 'Loading weather...',
    error: 'Failed to load weather data',
    retry: 'Retry',
    today: 'Today',
    tomorrow: 'Tomorrow',
    day_after: 'Day After',
    weekday_0: 'Sun',
    weekday_1: 'Mon',
    weekday_2: 'Tue',
    weekday_3: 'Wed',
    weekday_4: 'Thu',
    weekday_5: 'Fri',
    weekday_6: 'Sat',
  },
  error: {
    city_not_found: 'City not found',
    api_timeout: 'Weather service timed out',
    network: 'Network error, please try again',
  },
};
