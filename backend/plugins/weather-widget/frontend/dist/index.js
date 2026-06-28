(function(k,e){typeof exports=="object"&&typeof module<"u"?e(exports,require("vue"),require("@novus/plugin-shared"),require("ant-design-vue")):typeof define=="function"&&define.amd?define(["exports","vue","@novus/plugin-shared","ant-design-vue"],e):(k=typeof globalThis<"u"?globalThis:k||self,e(k.NovusPlugin_weather_widget={},k.Vue,k.NovusPluginShared,k.AntDesignVue))})(this,(function(k,e,t,Ke){"use strict";const ge=[{name:"北京",latitude:39.9042,longitude:116.4074,country:"China"},{name:"上海",latitude:31.2304,longitude:121.4737,country:"China"},{name:"广州",latitude:23.1291,longitude:113.2644,country:"China"},{name:"深圳",latitude:22.5431,longitude:114.0579,country:"China"},{name:"杭州",latitude:30.2741,longitude:120.1551,country:"China"},{name:"成都",latitude:30.5728,longitude:104.0668,country:"China"},{name:"武汉",latitude:30.5928,longitude:114.3055,country:"China"},{name:"南京",latitude:32.0603,longitude:118.7969,country:"China"},{name:"重庆",latitude:29.4316,longitude:106.9123,country:"China"},{name:"西安",latitude:34.3416,longitude:108.9398,country:"China"},{name:"苏州",latitude:31.299,longitude:120.5853,country:"China"},{name:"天津",latitude:39.3434,longitude:117.3616,country:"China"}],fe="novusai_weather_config",ue="novusai_weather_data",Je=6,Ze=600,ae="weather-widget",A={showCodeMessage:!1,showErrorMessage:!1,skipAuthRecovery:!0},v={city:"Shanghai",latitude:31.2304,longitude:121.4737,recentCities:[{name:"Shanghai",latitude:31.2304,longitude:121.4737,country:"China"}]},U=e.ref(!1);function he(n,o,l){return Math.max(o,Math.min(l,n))}function me(n){const o=n.trim().toLowerCase();return o?ge.find(l=>l.name.toLowerCase()===o)??null:null}function ve(n){const o=me(n);return o?{city:o.name,latitude:o.latitude,longitude:o.longitude,recentCities:[o]}:{...v,city:n,recentCities:[...v.recentCities]}}function et(){const n=window.location.pathname;return n.startsWith("/admin")?`/admin/plugins/${ae}/api`:n.startsWith("/tenant")?`/tenant/plugins/${ae}/api`:null}function S(){if(typeof t.buildPluginApiBase=="function")try{return t.buildPluginApiBase(ae)}catch{}const n=et();if(n)return n;throw new Error("Weather plugin host endpoint is unavailable")}function tt(n){return n==="fahrenheit"?"fahrenheit":"celsius"}function nt(){try{const n=localStorage.getItem(fe);if(n){const o=JSON.parse(n),l=typeof o.city=="string"?o.city.trim():"";if(l)return U.value=!0,O(l),ve(l)}}catch{}return U.value=!1,{...v,recentCities:[...v.recentCities]}}function O(n){try{const o={city:n};localStorage.setItem(fe,JSON.stringify(o)),U.value=!0}catch{}}function _e(){try{const n=localStorage.getItem(ue);if(n)return JSON.parse(n)}catch{}return null}function at(n){try{localStorage.setItem(ue,JSON.stringify(n))}catch{}}const g=e.ref(nt()),B=e.ref({}),X=e.ref(null),j=e.ref([]),H=e.ref([]),Y=e.ref(null),oe=e.ref(!1),re=e.ref(!0),ie=e.ref(null),le=e.ref(!1),G=e.ref(null),se=e.ref(!1),ce=e.ref(!1),P=e.ref(null);let N=null,Q=0,be=!1,ee=0,W=null,R=null;function ye(n,o){if(!n){ce.value=!1;return}ce.value=Date.now()-n>o}function ot(n,o,l){W&&(clearInterval(W),W=null),!(!o||Q<=0)&&(W=setInterval(()=>{l()},n))}function rt(){const n=e.computed(()=>g.value.city),o=e.computed(()=>g.value.recentCities),l=e.computed(()=>tt(B.value.temperature_unit)),d=e.computed(()=>he(B.value.forecast_days??3,1,7)),E=e.computed(()=>he(B.value.cache_ttl??Ze,60,3600)*1e3),C=e.computed(()=>Math.max(E.value,300*1e3));async function F(){try{const r=await t.requestClient.get(`${S()}/config`,A);r!=null&&r.config&&(B.value=r.config)}catch{B.value={}}}async function D(){var f;const r=(f=B.value.default_city)==null?void 0:f.trim();if(!r||U.value)return;const w=await h(r);if(w.length>0){const m=w[0];g.value.city=m.name,g.value.latitude=m.latitude,g.value.longitude=m.longitude,g.value.recentCities=[m],O(g.value.city);return}g.value.city=r,O(g.value.city)}async function I(){const r=g.value.city.trim();if(!U.value||!r||me(r))return;const w=await h(r);if(w.length>0){const f=w[0];g.value.city=f.name,g.value.latitude=f.latitude,g.value.longitude=f.longitude,g.value.recentCities=[f],O(g.value.city)}}async function V(){const r=++ee;R&&R.abort(),R=new AbortController,oe.value=!0,ie.value=null;const{latitude:w,longitude:f}=g.value,m=d.value;try{const[u,x,c,i]=await Promise.all([t.requestClient.get(`${S()}/current`,{...A,params:{lat:w,lon:f},signal:R.signal}),t.requestClient.get(`${S()}/forecast`,{...A,params:{lat:w,lon:f,days:m},signal:R.signal}).catch(()=>null),t.requestClient.get(`${S()}/hourly`,{...A,params:{lat:w,lon:f},signal:R.signal}).catch(()=>null),t.requestClient.get(`${S()}/air-quality`,{...A,params:{lat:w,lon:f},signal:R.signal}).catch(()=>null)]);if(r!==ee)return;X.value=(u==null?void 0:u.weather)??null,j.value=((x==null?void 0:x.forecast)??[]).slice(0,m),H.value=(c==null?void 0:c.hourly)??[],Y.value=(i==null?void 0:i.air_quality)??null,P.value=Date.now(),ye(P.value,C.value),at({current:X.value,forecast:j.value,hourly:H.value,airQuality:Y.value,timestamp:P.value})}catch(u){if(r!==ee)return;const x=u instanceof Error?u.message:String(u);if(x.toLowerCase().includes("aborted"))return;ie.value=x;const c=_e();c!=null&&c.current&&(X.value=c.current,j.value=c.forecast.slice(0,m),H.value=c.hourly,Y.value=c.airQuality,P.value=c.timestamp,ye(c.timestamp,C.value))}finally{r===ee&&(oe.value=!1,re.value=!1)}}async function h(r){const w=r.trim();if(!w)return[];try{const f=await t.requestClient.get(`${S()}/geocoding`,{...A,params:{name:w,count:8}});return(f==null?void 0:f.cities)??[]}catch{return[]}}async function $(r){g.value.city=r.name,g.value.latitude=r.latitude,g.value.longitude=r.longitude;const w=g.value.recentCities.filter(f=>!(Math.abs(f.latitude-r.latitude)<.01&&Math.abs(f.longitude-r.longitude)<.01));w.unshift(r),g.value.recentCities=w.slice(0,Je),O(g.value.city),se.value=!1,await V()}async function z(r){g.value.city=r.name,g.value.latitude=r.latitude,g.value.longitude=r.longitude,se.value=!1,await V()}async function M(){var r,w;if(!navigator.geolocation){G.value="locate_failed";return}le.value=!0,G.value=null;try{const f=await new Promise((c,i)=>{navigator.geolocation.getCurrentPosition(c,i,{enableHighAccuracy:!0,timeout:1e4,maximumAge:3e5})}),{latitude:m,longitude:u}=f.coords;let x=null;for(let c=0;c<2;c+=1){try{const i=await t.requestClient.get(`${S()}/geocoding`,{...A,params:{lat:m,lon:u}});if((r=i==null?void 0:i.cities)!=null&&r.length&&((w=i.cities[0])!=null&&w.name)){x=i.cities[0];break}}catch{}c===0&&await new Promise(i=>setTimeout(i,500))}x?await z(x):(await z({name:`${m.toFixed(2)}, ${u.toFixed(2)}`,latitude:m,longitude:u}),G.value="locate_fallback")}catch{G.value="locate_failed"}finally{le.value=!1}}async function _(){if(Q+=1,!be){be=!0;const r=_e();r!=null&&r.current&&(X.value=r.current,j.value=r.forecast,H.value=r.hourly,Y.value=r.airQuality,P.value=r.timestamp,re.value=!1),await F(),await I(),await D(),await V()}ot(E.value,B.value.auto_refresh??!0,V)}function K(){Q=Math.max(0,Q-1),Q<=0&&W&&(clearInterval(W),W=null)}return{cityName:n,recentCities:o,current:X,forecast:j,hourly:H,airQuality:Y,loading:oe,initialLoading:re,error:ie,locating:le,locateError:G,showCitySelector:se,isStale:ce,pluginConfig:B,temperatureUnit:l,forecastDays:d,lastUpdatedAt:P,fetchAll:V,searchCity:h,selectCity:$,geolocate:M,mount:_,unmount:K}}function ke(){return N||(N=rt()),e.onMounted(()=>{N==null||N.mount()}),e.onBeforeUnmount(()=>{N==null||N.unmount()}),N}function Ee(n,o){return o?n.weather_text_zh||n.weather_text_en||"--":n.weather_text_en||n.weather_text_zh||"--"}function it(n,o){return n==null||Number.isNaN(n)?null:o==="fahrenheit"?n*9/5+32:n}function y(n,o,l=0){const d=it(n,o);return d==null?"--":d.toFixed(l)}function lt(n){return n==="fahrenheit"?"F":"C"}function Ne(n,o,l=1){return n==null||Number.isNaN(n)?"--":(o==="fahrenheit"?n*.621371:n).toFixed(l)}function Ce(n){return[n.admin1,n.country].filter(Boolean).join(" · ")}function Ve(n,o){return n?new Intl.DateTimeFormat(o,{hour:"2-digit",minute:"2-digit"}).format(n):"--:--"}function $e(n){if(!n)return"--:--";const o=n.includes("T")?n.split("T")[1]:n;return o?o.slice(0,5):"--:--"}function ze(n){return n==null?"na":n<=50?"good":n<=100?"moderate":n<=150?"unhealthy_sensitive":n<=200?"unhealthy":n<=300?"very_unhealthy":"hazardous"}function Be(n){return n==null?"#A7B3CC":n<=50?"#47D16D":n<=100?"#EABD43":n<=150?"#F49D58":n<=200?"#F06B67":n<=300?"#A47DE8":"#D45A8A"}function De(n,o,l){if(o===0)return l("plugin.weather-widget.ui.today");if(o===1)return l("plugin.weather-widget.ui.tomorrow");if(o===2)return l("plugin.weather-widget.ui.day_after");const d=new Date(n).getDay();return l(`plugin.weather-widget.ui.weekday_${d}`)}const Ie={0:{icon:"sun",nightIcon:"moon",scene:"clear"},1:{icon:"sun",nightIcon:"moon",scene:"clear"},2:{icon:"cloud-sun",nightIcon:"cloud-moon",scene:"cloudy"},3:{icon:"cloud",scene:"cloudy"},45:{icon:"cloud-fog",scene:"fog"},48:{icon:"cloud-fog",scene:"fog"},51:{icon:"cloud-drizzle",scene:"drizzle"},53:{icon:"cloud-drizzle",scene:"drizzle"},55:{icon:"cloud-drizzle",scene:"drizzle"},56:{icon:"cloud-drizzle",scene:"drizzle"},57:{icon:"cloud-drizzle",scene:"drizzle"},61:{icon:"cloud-rain",scene:"rain"},63:{icon:"cloud-rain",scene:"rain"},65:{icon:"cloud-rain",scene:"rain"},66:{icon:"cloud-rain",scene:"rain"},67:{icon:"cloud-rain",scene:"rain"},71:{icon:"snowflake",scene:"snow"},73:{icon:"snowflake",scene:"snow"},75:{icon:"snowflake",scene:"snow"},77:{icon:"snowflake",scene:"snow"},80:{icon:"cloud-rain",scene:"rain"},81:{icon:"cloud-rain",scene:"rain"},82:{icon:"cloud-rain",scene:"rain"},85:{icon:"snowflake",scene:"snow"},86:{icon:"snowflake",scene:"snow"},95:{icon:"cloud-lightning",scene:"thunderstorm"},96:{icon:"cloud-lightning",scene:"thunderstorm"},99:{icon:"cloud-lightning",scene:"thunderstorm"}},Te={icon:"cloud",scene:"cloudy"};function Le(n,o=!0){const l=Ie[n]??Te;return{icon:!o&&l.nightIcon?l.nightIcon:l.icon,scene:l.scene}}const st={"clear-day":{bgClass:"wx-bg--clear-day",scene:"sun"},"clear-night":{bgClass:"wx-bg--clear-night",scene:"moon-star"},"cloudy-day":{bgClass:"wx-bg--cloudy-day",scene:"cloud"},"cloudy-night":{bgClass:"wx-bg--cloudy-night",scene:"cloud"},"fog-day":{bgClass:"wx-bg--fog",scene:"fog"},"fog-night":{bgClass:"wx-bg--fog",scene:"fog"},"drizzle-day":{bgClass:"wx-bg--rain-day",scene:"rain"},"drizzle-night":{bgClass:"wx-bg--rain-night",scene:"rain"},"rain-day":{bgClass:"wx-bg--rain-day",scene:"rain"},"rain-night":{bgClass:"wx-bg--rain-night",scene:"rain"},"snow-day":{bgClass:"wx-bg--snow-day",scene:"snow"},"snow-night":{bgClass:"wx-bg--snow-night",scene:"snow"},"thunderstorm-day":{bgClass:"wx-bg--thunder",scene:"thunder"},"thunderstorm-night":{bgClass:"wx-bg--thunder",scene:"thunder"}};function Ae(n,o=!0){const l=Ie[n]??Te,d=o?"day":"night",E=`${l.scene}-${d}`;return st[E]??{bgClass:"wx-bg--cloudy-day",scene:"cloud"}}const ct={class:"wx-dashboard-shell"},dt={class:"wx-dashboard__topbar"},pt={class:"wx-dashboard__eyebrow"},xt=["disabled","aria-label"],wt={class:"wx-dashboard__hero"},gt={class:"wx-dashboard__hero-main"},ft={class:"wx-dashboard__temp"},ut={class:"wx-dashboard__condition-wrap"},ht={class:"wx-dashboard__condition-line"},mt={class:"wx-dashboard__icon-wrap"},_t={class:"wx-dashboard__condition"},bt={class:"wx-dashboard__meta"},yt={class:"wx-dashboard__chip-row"},kt={key:0,class:"wx-dashboard__forecast-ribbon"},Et={class:"wx-dashboard__forecast-head"},Nt={class:"wx-dashboard__forecast-range"},Ct={class:"wx-dashboard__forecast-text"},Vt={key:1,class:"wx-dashboard-skeleton"},$t={key:2,class:"wx-dashboard-empty"},zt={class:"wx-dashboard-empty__title"},Bt={key:0,class:"wx-dashboard-empty__desc"},Dt=e.defineComponent({__name:"WeatherDashboardWidget",setup(n){const{cityName:o,current:l,forecast:d,airQuality:E,loading:C,initialLoading:F,error:D,isStale:I,lastUpdatedAt:V,temperatureUnit:h,fetchAll:$}=ke(),z=e.computed(()=>t.$t("plugin.weather-widget._meta.lang")==="zh"),M=e.computed(()=>d.value.slice(0,3)),_=e.computed(()=>l.value?Ae(l.value.weather_code,l.value.is_day):{bgClass:"wx-bg--cloudy-day",scene:"cloud"}),K=e.computed(()=>Ve(V.value,z.value?"zh-CN":"en-US")),r=e.computed(()=>I.value?t.$t("plugin.weather-widget.ui.cached_data"):t.$t("plugin.weather-widget.ui.live_data")),w=e.computed(()=>h.value==="fahrenheit"?t.$t("plugin.weather-widget.ui.unit_mph"):t.$t("plugin.weather-widget.ui.unit_kmh")),f=e.computed(()=>{var x,c,i;return l.value?[{key:"humidity",label:t.$t("plugin.weather-widget.ui.humidity"),note:void 0,tone:void 0,value:`${l.value.humidity??"--"}%`,wide:!1},{key:"wind",label:t.$t("plugin.weather-widget.ui.wind_speed"),note:void 0,tone:void 0,value:`${Ne(l.value.wind_speed,h.value)} ${w.value}`,wide:!1},{key:"aqi",label:t.$t("plugin.weather-widget.ui.aqi"),value:`${((x=E.value)==null?void 0:x.aqi)??"--"}`,note:t.$t(`plugin.weather-widget.aqi_level.${ze((c=E.value)==null?void 0:c.aqi)}`),tone:Be((i=E.value)==null?void 0:i.aqi),wide:!0}]:[]});function m(x){return Ee(x,z.value)}function u(x,c=!0){return Le(x,c).icon}return(x,c)=>(e.openBlock(),e.createElementBlock("div",ct,[e.unref(l)?(e.openBlock(),e.createElementBlock("section",{key:0,class:e.normalizeClass(["wx-dashboard wx-noise",[_.value.bgClass,`wx-scene--${_.value.scene}`]])},[c[2]||(c[2]=e.createStaticVNode('<div class="wx-panel__veil wx-panel__veil--dashboard"></div><div class="wx-scene wx-scene--dashboard" aria-hidden="true"><span class="wx-scene__orb"></span><span class="wx-scene__cloud wx-scene__cloud--1"></span><span class="wx-scene__cloud wx-scene__cloud--2"></span><span class="wx-scene__spark wx-scene__spark--1"></span><span class="wx-scene__spark wx-scene__spark--2"></span><span class="wx-scene__drop wx-scene__drop--1"></span><span class="wx-scene__drop wx-scene__drop--2"></span><span class="wx-scene__flake wx-scene__flake--1"></span><span class="wx-scene__mist wx-scene__mist--1"></span><span class="wx-scene__flash"></span></div>',2)),e.createElementVNode("div",dt,[e.createElementVNode("div",pt,[e.createElementVNode("span",null,e.toDisplayString(e.unref(o)),1),e.createElementVNode("span",null,e.toDisplayString(r.value),1)]),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref(C),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.refresh"),onClick:c[0]||(c[0]=(...i)=>e.unref($)&&e.unref($)(...i))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(C)?"lucide:loader-2":"lucide:refresh-cw",class:e.normalizeClass(e.unref(C)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,xt)]),e.createElementVNode("div",wt,[e.createElementVNode("div",gt,[e.createElementVNode("div",ft,e.toDisplayString(e.unref(y)(e.unref(l).temperature,e.unref(h)))+"° ",1),e.createElementVNode("div",ut,[e.createElementVNode("div",ht,[e.createElementVNode("div",mt,[e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${u(e.unref(l).weather_code,e.unref(l).is_day)}`,class:"wx-dashboard__icon"},null,8,["icon"])]),e.createElementVNode("div",_t,e.toDisplayString(m(e.unref(l))),1)]),e.createElementVNode("div",bt,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.feels_like"))+" "+e.toDisplayString(e.unref(y)(e.unref(l).apparent_temperature,e.unref(h)))+"° ",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.last_updated"))+" "+e.toDisplayString(K.value),1)])])])]),e.createElementVNode("div",yt,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(f.value,i=>(e.openBlock(),e.createElementBlock("article",{key:i.key,class:e.normalizeClass(["wx-dashboard__chip",i.wide?"wx-dashboard__chip--wide":""])},[e.createElementVNode("span",null,e.toDisplayString(i.label),1),e.createElementVNode("strong",{style:e.normalizeStyle(i.tone?{color:i.tone}:void 0)},e.toDisplayString(i.value),5),i.note?(e.openBlock(),e.createElementBlock("small",{key:0,style:e.normalizeStyle(i.tone?{color:i.tone}:void 0)},e.toDisplayString(i.note),5)):e.createCommentVNode("",!0)],2))),128))]),M.value.length>0?(e.openBlock(),e.createElementBlock("div",kt,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(M.value,(i,q)=>(e.openBlock(),e.createElementBlock("article",{key:i.date,class:"wx-dashboard__forecast-pill"},[e.createElementVNode("div",Et,[e.createElementVNode("span",null,e.toDisplayString(e.unref(De)(i.date,q,e.unref(t.$t))),1),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${u(i.weather_code,!0)}`,class:"size-4"},null,8,["icon"])]),e.createElementVNode("div",Nt,[e.createElementVNode("span",null,e.toDisplayString(e.unref(y)(i.temp_max,e.unref(h)))+"°",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(y)(i.temp_min,e.unref(h)))+"°",1)]),e.createElementVNode("div",Ct,e.toDisplayString(m(i)),1)]))),128))])):e.createCommentVNode("",!0)],2)):e.unref(F)?(e.openBlock(),e.createElementBlock("div",Vt,[...c[3]||(c[3]=[e.createStaticVNode('<div class="wx-skeleton wx-skeleton--lg"></div><div class="wx-dashboard-skeleton__row"><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div></div><div class="wx-dashboard-skeleton__row"><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div></div>',3)])])):(e.openBlock(),e.createElementBlock("div",$t,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:cloud-off",class:"size-10 text-muted-foreground"}),e.createElementVNode("div",zt,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.error")),1),e.unref(D)?(e.openBlock(),e.createElementBlock("div",Bt,e.toDisplayString(e.unref(D)),1)):e.createCommentVNode("",!0),e.createElementVNode("button",{type:"button",class:"wx-action-btn",onClick:c[1]||(c[1]=(...i)=>e.unref($)&&e.unref($)(...i))},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:refresh-cw",class:"size-4"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.retry")),1)])]))]))}}),It=["aria-label","aria-expanded"],Tt={class:"wx-trigger__icon-wrap"},Lt={class:"wx-trigger__copy"},At={key:"city-selector",class:"wx-city-panel"},St={class:"wx-city-panel__head"},Wt=["aria-label"],Rt=["aria-label"],Ft={class:"wx-city-panel__summary"},Mt={class:"wx-city-panel__label"},qt={class:"wx-search"},Pt=["value","placeholder"],Ut={class:"wx-city-list"},Ot={key:0},Xt={key:0,class:"wx-state-line"},jt=["onClick"],Ht={class:"wx-city-chip__main"},Yt={class:"truncate"},Gt={key:0,class:"wx-city-chip__meta"},Qt={key:1,class:"wx-state-line"},Kt=["disabled","aria-label"],Jt={key:1,class:"wx-state-line wx-state-line--error"},Zt={key:2,class:"wx-city-group"},vt={class:"wx-city-grid"},en=["onClick"],tn={class:"truncate"},nn={class:"wx-city-group"},an={class:"wx-city-grid"},on=["onClick"],rn={class:"truncate"},ln={key:"weather-main",class:"wx-main-panel"},sn={key:0,class:"wx-skeleton-wrap"},cn={key:1,class:"wx-empty"},dn={class:"wx-main-head"},pn=["aria-label"],xn={class:"truncate"},wn={class:"wx-head-actions"},gn={class:"wx-status-chip"},fn=["disabled","aria-label"],un=["disabled","aria-label"],hn={class:"wx-hero"},mn={class:"wx-hero__eyebrow"},_n={class:"wx-hero__body"},bn={class:"wx-hero__copy"},yn={class:"wx-hero__temp"},kn={class:"wx-hero__text"},En={class:"wx-hero__sub"},Nn={key:0},Cn={class:"wx-hero__meta"},Vn={class:"wx-hero__icon-shell"},$n={class:"wx-hero__unit"},zn={key:0,class:"wx-stale-badge"},Bn={class:"wx-chip-grid"},Dn={key:0,class:"wx-hourly-band"},In={class:"wx-section-head wx-section-head--inline"},Tn={class:"wx-hour-item__time"},Ln={class:"wx-hour-item__temp"},An={class:"wx-sun-strip"},Sn={class:"wx-sun-chip"},Wn={class:"wx-sun-chip"},Rn={key:1,class:"wx-forecast-sheet"},Fn={class:"wx-section-head wx-section-head--inline"},Mn={class:"wx-forecast-row__day"},qn={class:"wx-forecast-row__temp"},Pn=e.defineComponent({__name:"WeatherHeaderWidget",setup(n){const{cityName:o,recentCities:l,current:d,forecast:E,hourly:C,airQuality:F,loading:D,initialLoading:I,error:V,locating:h,locateError:$,showCitySelector:z,isStale:M,temperatureUnit:_,forecastDays:K,lastUpdatedAt:r,fetchAll:w,searchCity:f,selectCity:m,geolocate:u}=ke(),x=e.ref(!1),c=e.ref(""),i=e.ref([]),q=e.ref(!1),Re=e.ref(null),de=e.ref(null),pe=e.ref(null),Fe=e.ref({});let J=null,te=null;const Me=e.computed(()=>t.$t("plugin.weather-widget._meta.lang")==="zh"),qe=e.computed(()=>lt(_.value)),Xn=e.computed(()=>_.value==="fahrenheit"?t.$t("plugin.weather-widget.ui.unit_mph"):t.$t("plugin.weather-widget.ui.unit_kmh")),Z=e.computed(()=>E.value[0]??null),Pe=e.computed(()=>E.value.slice(0,Math.min(K.value,3))),Ue=e.computed(()=>C.value.slice(0,6)),Oe=e.computed(()=>M.value?t.$t("plugin.weather-widget.ui.cached_data"):t.$t("plugin.weather-widget.ui.live_data")),jn=e.computed(()=>Ve(r.value,Me.value?"zh-CN":"en-US")),Xe=e.computed(()=>d.value?Ae(d.value.weather_code,d.value.is_day):{bgClass:"wx-bg--cloudy-day",scene:"cloud"}),Hn=e.computed(()=>{var p,s,b;return d.value?[{key:"humidity",label:t.$t("plugin.weather-widget.ui.humidity"),note:void 0,tone:void 0,value:`${d.value.humidity??"--"}%`},{key:"wind",label:t.$t("plugin.weather-widget.ui.wind_speed"),note:void 0,tone:void 0,value:`${Ne(d.value.wind_speed,_.value)} ${Xn.value}`},{key:"uv",label:t.$t("plugin.weather-widget.ui.uv_index"),note:void 0,tone:void 0,value:`${d.value.uv_index??"--"}`},{key:"aqi",label:t.$t("plugin.weather-widget.ui.aqi"),value:`${((p=F.value)==null?void 0:p.aqi)??"--"}`,note:Gn((s=F.value)==null?void 0:s.aqi),tone:Be((b=F.value)==null?void 0:b.aqi)}]:[]});function ne(p,s=!0){return Le(p,s).icon}function je(p){return Ee(p,Me.value)}function Yn(p,s){return s?t.$t("plugin.weather-widget.ui.now"):p}function Gn(p){const s=ze(p);return t.$t(`plugin.weather-widget.aqi_level.${s}`)}function Qn(){return Math.max(Math.min(360,window.innerWidth-20),0)}function Kn(){var Qe;const p=de.value;if(!p||!p.isConnected){x.value=!1;return}const s=4,b=10,T=p.getBoundingClientRect(),a=((Qe=pe.value)==null?void 0:Qe.offsetWidth)??Qn(),L=Math.max(window.innerWidth-a-b,b),ea=Math.min(Math.max(T.right-a,b),L);Fe.value={left:`${ea}px`,top:`${Math.max(T.bottom+s,b)}px`}}function He(p){var b,T;if(!x.value)return;const s=p.target;s&&((b=de.value)!=null&&b.contains(s)||(T=pe.value)!=null&&T.contains(s)||(x.value=!1))}function Ye(p){p.key==="Escape"&&(x.value=!1)}function Jn(){xe();const p=()=>{Kn(),te=requestAnimationFrame(p)};p(),document.addEventListener("pointerdown",He,!0),window.addEventListener("keydown",Ye)}function xe(){te!=null&&(cancelAnimationFrame(te),te=null),document.removeEventListener("pointerdown",He,!0),window.removeEventListener("keydown",Ye)}function Zn(){x.value=!x.value}function vn(p){if(c.value=p,J&&clearTimeout(J),!p.trim()){q.value=!1,i.value=[];return}q.value=!0,J=setTimeout(async()=>{i.value=await f(p.trim()),q.value=!1},260)}async function we(p){c.value="",i.value=[],await m(p)}function Ge(){e.nextTick(()=>{const p=Re.value;if(!p)return;const s=p.querySelector(".wx-hour-item--active");s&&p.scrollTo({left:Math.max(s.offsetLeft-16,0),behavior:"smooth"})})}return e.watch(C,()=>{x.value&&Ge()}),e.watch(x,p=>{if(p){Ge(),e.nextTick(()=>{Jn()});return}xe()}),e.onBeforeUnmount(()=>{J&&clearTimeout(J),xe()}),(p,s)=>(e.openBlock(),e.createElementBlock(e.Fragment,null,[e.createVNode(e.unref(Ke.Tooltip),{title:e.unref(t.$t)("plugin.weather-widget.ui.open_weather"),placement:"bottom"},{default:e.withCtx(()=>[e.createElementVNode("button",{ref_key:"triggerRef",ref:de,type:"button",class:"wx-trigger","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.open_weather"),"aria-expanded":x.value,onClick:Zn},[e.createElementVNode("span",Tt,[e.unref(d)&&!e.unref(I)?(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:0,icon:`lucide:${ne(e.unref(d).weather_code,e.unref(d).is_day)}`,class:"wx-trigger__icon"},null,8,["icon"])):e.unref(I)?(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:1,icon:"lucide:loader-2",class:"wx-trigger__icon animate-spin"})):(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:2,icon:"lucide:cloud-off",class:"wx-trigger__icon"}))]),e.createElementVNode("span",Lt,[e.createElementVNode("small",null,e.toDisplayString(e.unref(o)),1),e.createElementVNode("strong",null,[e.unref(d)&&!e.unref(I)?(e.openBlock(),e.createElementBlock(e.Fragment,{key:0},[e.createTextVNode(e.toDisplayString(e.unref(y)(e.unref(d).temperature,e.unref(_)))+"° ",1)],64)):(e.openBlock(),e.createElementBlock(e.Fragment,{key:1},[e.createTextVNode(" -- ")],64))])])],8,It)]),_:1},8,["title"]),(e.openBlock(),e.createBlock(e.Teleport,{to:"body"},[x.value?(e.openBlock(),e.createElementBlock("div",{key:0,class:"weather-popover-immersive-overlay",style:e.normalizeStyle(Fe.value)},[e.createElementVNode("section",{ref_key:"panelRef",ref:pe,class:e.normalizeClass(["wx-panel wx-noise",[Xe.value.bgClass,`wx-scene--${Xe.value.scene}`]])},[s[10]||(s[10]=e.createElementVNode("div",{class:"wx-panel__veil"},null,-1)),e.createVNode(e.Transition,{name:"wx-fade-slide",mode:"out-in"},{default:e.withCtx(()=>{var b,T;return[e.unref(z)?(e.openBlock(),e.createElementBlock("div",At,[e.createElementVNode("header",St,[e.createElementVNode("button",{type:"button",class:"wx-icon-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.back"),onClick:s[0]||(s[0]=a=>z.value=!1)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:chevron-left",class:"size-4"})],8,Wt),e.createElementVNode("h3",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.change_city")),1),e.createElementVNode("button",{type:"button",class:"wx-icon-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.close"),onClick:s[1]||(s[1]=a=>x.value=!1)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:x",class:"size-4"})],8,Rt)]),e.createElementVNode("div",Ft,[e.createElementVNode("span",Mt,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.current_city")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref(o)),1)]),e.createElementVNode("label",qt,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:search",class:"size-4 opacity-70"}),e.createElementVNode("input",{value:c.value,placeholder:e.unref(t.$t)("plugin.weather-widget.ui.search_city"),onInput:s[2]||(s[2]=a=>vn(a.target.value))},null,40,Pt)]),e.createElementVNode("div",Ut,[c.value.trim()?(e.openBlock(),e.createElementBlock("div",Ot,[q.value?(e.openBlock(),e.createElementBlock("div",Xt,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:loader-2",class:"size-4 animate-spin"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.loading")),1)])):e.createCommentVNode("",!0),(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(i.value,a=>(e.openBlock(),e.createElementBlock("button",{key:`search-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>we(a)},[e.createElementVNode("span",Ht,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:map-pin",class:"size-3.5 opacity-65"}),e.createElementVNode("span",Yt,e.toDisplayString(a.name),1)]),e.unref(Ce)(a)?(e.openBlock(),e.createElementBlock("span",Gt,e.toDisplayString(e.unref(Ce)(a)),1)):e.createCommentVNode("",!0)],8,jt))),128)),!q.value&&i.value.length===0?(e.openBlock(),e.createElementBlock("div",Qt,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.error.city_not_found")),1)):e.createCommentVNode("",!0)])):e.createCommentVNode("",!0),e.createElementVNode("button",{type:"button",class:"wx-locate-btn",disabled:e.unref(h),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.auto_locate"),onClick:s[3]||(s[3]=(...a)=>e.unref(u)&&e.unref(u)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(h)?"lucide:loader-2":"lucide:locate",class:e.normalizeClass(e.unref(h)?"size-4 animate-spin":"size-4")},null,8,["icon","class"]),e.createTextVNode(" "+e.toDisplayString(e.unref(h)?e.unref(t.$t)("plugin.weather-widget.ui.locating"):e.unref(t.$t)("plugin.weather-widget.ui.auto_locate")),1)],8,Kt),e.unref($)?(e.openBlock(),e.createElementBlock("div",Jt,e.toDisplayString(e.unref(t.$t)(`plugin.weather-widget.error.${e.unref($)}`)),1)):e.createCommentVNode("",!0),e.unref(l).length>0?(e.openBlock(),e.createElementBlock("div",Zt,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.recent_cities")),1),e.createElementVNode("div",vt,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(e.unref(l),a=>(e.openBlock(),e.createElementBlock("button",{key:`recent-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>we(a)},[e.createElementVNode("span",tn,e.toDisplayString(a.name),1)],8,en))),128))])])):e.createCommentVNode("",!0),e.createElementVNode("div",nn,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.popular_cities")),1),e.createElementVNode("div",an,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(e.unref(ge),a=>(e.openBlock(),e.createElementBlock("button",{key:`popular-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>we(a)},[e.createElementVNode("span",rn,e.toDisplayString(a.name),1)],8,on))),128))])])])])):(e.openBlock(),e.createElementBlock("div",ln,[e.unref(I)&&!e.unref(d)?(e.openBlock(),e.createElementBlock("div",sn,[...s[8]||(s[8]=[e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--lg"},null,-1),e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--md"},null,-1),e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--grid"},null,-1)])])):e.unref(V)&&!e.unref(d)?(e.openBlock(),e.createElementBlock("div",cn,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:cloud-off",class:"size-10 opacity-65"}),e.createElementVNode("p",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.error")),1),e.createElementVNode("button",{type:"button",class:"wx-action-btn",onClick:s[4]||(s[4]=(...a)=>e.unref(w)&&e.unref(w)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:refresh-cw",class:"size-4"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.retry")),1)])])):e.unref(d)?(e.openBlock(),e.createElementBlock(e.Fragment,{key:2},[e.createElementVNode("header",dn,[e.createElementVNode("button",{type:"button",class:"wx-city-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.change_city"),onClick:s[5]||(s[5]=a=>z.value=!0)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:map-pin",class:"size-3.5 opacity-70"}),e.createElementVNode("span",xn,e.toDisplayString(e.unref(o)),1),e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:chevron-down",class:"size-3.5 opacity-60"})],8,pn),e.createElementVNode("div",wn,[e.createElementVNode("span",gn,e.toDisplayString(Oe.value),1),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref(h),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.auto_locate"),onClick:s[6]||(s[6]=(...a)=>e.unref(u)&&e.unref(u)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(h)?"lucide:loader-2":"lucide:locate",class:e.normalizeClass(e.unref(h)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,fn),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref(D),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.refresh"),onClick:s[7]||(s[7]=(...a)=>e.unref(w)&&e.unref(w)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(D)?"lucide:loader-2":"lucide:refresh-cw",class:e.normalizeClass(e.unref(D)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,un)])]),s[9]||(s[9]=e.createElementVNode("div",{class:"wx-scene","aria-hidden":"true"},[e.createElementVNode("span",{class:"wx-scene__orb"}),e.createElementVNode("span",{class:"wx-scene__cloud wx-scene__cloud--1"}),e.createElementVNode("span",{class:"wx-scene__cloud wx-scene__cloud--2"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--1"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--2"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--3"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--1"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--2"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--3"}),e.createElementVNode("span",{class:"wx-scene__flake wx-scene__flake--1"}),e.createElementVNode("span",{class:"wx-scene__flake wx-scene__flake--2"}),e.createElementVNode("span",{class:"wx-scene__mist wx-scene__mist--1"}),e.createElementVNode("span",{class:"wx-scene__mist wx-scene__mist--2"}),e.createElementVNode("span",{class:"wx-scene__flash"})],-1)),e.createElementVNode("div",hn,[e.createElementVNode("div",mn,[e.createElementVNode("span",null,e.toDisplayString(Oe.value),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.last_updated"))+" "+e.toDisplayString(jn.value),1)]),e.createElementVNode("div",_n,[e.createElementVNode("div",bn,[e.createElementVNode("div",yn,e.toDisplayString(e.unref(y)(e.unref(d).temperature,e.unref(_)))+"° ",1),e.createElementVNode("div",kn,e.toDisplayString(je(e.unref(d))),1),e.createElementVNode("div",En,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.feels_like"))+" "+e.toDisplayString(e.unref(y)(e.unref(d).apparent_temperature,e.unref(_)))+"°"+e.toDisplayString(qe.value),1),Z.value?(e.openBlock(),e.createElementBlock("span",Nn,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.high_short"))+" "+e.toDisplayString(e.unref(y)(Z.value.temp_max,e.unref(_)))+"° / "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.low_short"))+" "+e.toDisplayString(e.unref(y)(Z.value.temp_min,e.unref(_)))+"° ",1)):e.createCommentVNode("",!0)])]),e.createElementVNode("div",Cn,[e.createElementVNode("div",Vn,[e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ne(e.unref(d).weather_code,e.unref(d).is_day)}`,class:"wx-hero__icon"},null,8,["icon"])]),e.createElementVNode("span",$n,e.toDisplayString(qe.value),1)])]),e.unref(M)?(e.openBlock(),e.createElementBlock("div",zn,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.data_stale")),1)):e.createCommentVNode("",!0)]),e.createElementVNode("section",Bn,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Hn.value,a=>(e.openBlock(),e.createElementBlock("article",{key:a.key,class:"wx-chip"},[e.createElementVNode("span",null,e.toDisplayString(a.label),1),e.createElementVNode("strong",{style:e.normalizeStyle(a.tone?{color:a.tone}:void 0)},e.toDisplayString(a.value),5),a.note?(e.openBlock(),e.createElementBlock("small",{key:0,style:e.normalizeStyle(a.tone?{color:a.tone}:void 0)},e.toDisplayString(a.note),5)):e.createCommentVNode("",!0)]))),128))]),Ue.value.length>0?(e.openBlock(),e.createElementBlock("section",Dn,[e.createElementVNode("div",In,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.hourly_forecast")),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.hourly_digest")),1)]),e.createElementVNode("div",{ref_key:"hourlyScrollRef",ref:Re,class:"wx-hourly-scroll"},[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Ue.value,(a,L)=>(e.openBlock(),e.createElementBlock("article",{key:`hour-${L}`,class:e.normalizeClass(["wx-hour-item",a.is_current?"wx-hour-item--active":""])},[e.createElementVNode("span",Tn,e.toDisplayString(Yn(a.time,a.is_current)),1),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ne(a.weather_code,e.unref(d).is_day)}`,class:"size-4"},null,8,["icon"]),e.createElementVNode("span",Ln,e.toDisplayString(e.unref(y)(a.temperature,e.unref(_)))+"° ",1)],2))),128))],512)])):e.createCommentVNode("",!0),e.createElementVNode("div",An,[e.createElementVNode("article",Sn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.sunrise")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref($e)((b=Z.value)==null?void 0:b.sunrise)),1)]),e.createElementVNode("article",Wn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.sunset")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref($e)((T=Z.value)==null?void 0:T.sunset)),1)])]),Pe.value.length>0?(e.openBlock(),e.createElementBlock("section",Rn,[e.createElementVNode("div",Fn,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.forecast")),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.forecast_digest")),1)]),(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Pe.value,(a,L)=>(e.openBlock(),e.createElementBlock("article",{key:a.date,class:"wx-forecast-row"},[e.createElementVNode("div",Mn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(De)(a.date,L,e.unref(t.$t))),1),e.createElementVNode("small",null,e.toDisplayString(je(a)),1)]),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ne(a.weather_code,e.unref(d).is_day)}`,class:"size-4"},null,8,["icon"]),e.createElementVNode("div",qn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.high_short"))+" "+e.toDisplayString(e.unref(y)(a.temp_max,e.unref(_)))+"° ",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.low_short"))+" "+e.toDisplayString(e.unref(y)(a.temp_min,e.unref(_)))+"° ",1)])]))),128))])):e.createCommentVNode("",!0)],64)):e.createCommentVNode("",!0)]))]}),_:1})],2)],4)):e.createCommentVNode("",!0)]))],64))}}),Se={_meta:{lang:"zh"},ui:{temperature:"温度",feels_like:"体感温度",humidity:"湿度",wind_speed:"风速",uv_index:"紫外线",aqi:"空气质量",sunrise:"日出",sunset:"日落",hourly_forecast:"小时预报",hourly_digest:"未来几小时走势",forecast:"未来预报",forecast_digest:"接下来几天概览",current_conditions:"当前天气",current_city:"当前城市",last_updated:"更新于",live_data:"实时",cached_data:"缓存",change_city:"切换城市",search_city:"搜索城市...",recent_cities:"最近城市",popular_cities:"热门城市",auto_locate:"自动定位",locating:"定位中...",loading:"加载天气中...",error:"天气数据获取失败",retry:"重试",refresh:"刷新天气",open_weather:"打开天气面板",back:"返回",close:"关闭",today:"今天",tomorrow:"明天",day_after:"后天",now:"现在",weekday_0:"周日",weekday_1:"周一",weekday_2:"周二",weekday_3:"周三",weekday_4:"周四",weekday_5:"周五",weekday_6:"周六",data_stale:"数据可能已过期",high_short:"高",low_short:"低",unit_kmh:"公里/小时",unit_mph:"英里/小时"},error:{city_not_found:"未找到该城市",api_timeout:"天气服务请求超时",network:"网络错误，请稍后重试",locate_failed:"定位失败，请检查权限",locate_fallback:"无法识别城市，使用坐标定位"},aqi_level:{good:"优",moderate:"良",unhealthy_sensitive:"轻度",unhealthy:"中度",very_unhealthy:"重度",hazardous:"严重",na:"--"}},We={_meta:{lang:"en"},ui:{temperature:"Temperature",feels_like:"Feels Like",humidity:"Humidity",wind_speed:"Wind",uv_index:"UV Index",aqi:"Air Quality",sunrise:"Sunrise",sunset:"Sunset",hourly_forecast:"Hourly",hourly_digest:"Next few hours",forecast:"Forecast",forecast_digest:"Upcoming days",current_conditions:"Current Conditions",current_city:"Current City",last_updated:"Updated",live_data:"Live",cached_data:"Cached",change_city:"Change City",search_city:"Search city...",recent_cities:"Recent Cities",popular_cities:"Popular Cities",auto_locate:"Auto Locate",locating:"Locating...",loading:"Loading weather...",error:"Failed to load weather data",retry:"Retry",refresh:"Refresh weather",open_weather:"Open weather panel",back:"Back",close:"Close",today:"Today",tomorrow:"Tomorrow",day_after:"Day After",now:"Now",weekday_0:"Sun",weekday_1:"Mon",weekday_2:"Tue",weekday_3:"Wed",weekday_4:"Thu",weekday_5:"Fri",weekday_6:"Sat",data_stale:"Data may be outdated",high_short:"H",low_short:"L",unit_kmh:"km/h",unit_mph:"mph"},error:{city_not_found:"City not found",api_timeout:"Weather service timed out",network:"Network error, please try again",locate_failed:"Location failed, check permissions",locate_fallback:"Could not identify city, using coordinates"},aqi_level:{good:"Good",moderate:"Moderate",unhealthy_sensitive:"Sensitive",unhealthy:"Unhealthy",very_unhealthy:"Very Unhealthy",hazardous:"Hazardous",na:"--"}},Un=[`
.weather-popover-immersive-overlay {
  position: fixed;
  width: min(360px, calc(100vw - 20px));
  max-width: calc(100vw - 20px);
  z-index: 2400;
  pointer-events: auto;
  will-change: top, left;
}

.wx-panel,
.wx-dashboard {
  --wx-bg-top: #45617f;
  --wx-bg-bottom: #8da7c1;
  --wx-accent: rgba(255, 255, 255, 0.22);
  --wx-surface: rgba(255, 255, 255, 0.12);
  --wx-surface-strong: rgba(255, 255, 255, 0.18);
  --wx-outline: rgba(255, 255, 255, 0.14);
  --wx-outline-strong: rgba(255, 255, 255, 0.22);
  --wx-text-primary: #f8fbff;
  --wx-text-secondary: rgba(248, 251, 255, 0.76);
  --wx-text-faint: rgba(248, 251, 255, 0.54);
  --wx-shadow: 0 28px 68px rgba(15, 23, 42, 0.34);
  position: relative;
  overflow: hidden;
  color: var(--wx-text-primary);
  background: linear-gradient(155deg, var(--wx-bg-top), var(--wx-bg-bottom));
}

.wx-bg--clear-day {
  --wx-bg-top: #2962ef;
  --wx-bg-bottom: #70c0ff;
  --wx-accent: rgba(253, 224, 71, 0.28);
}

.wx-bg--clear-night {
  --wx-bg-top: #0b1634;
  --wx-bg-bottom: #1c396d;
  --wx-accent: rgba(226, 232, 240, 0.22);
}

.wx-bg--cloudy-day {
  --wx-bg-top: #3f5f80;
  --wx-bg-bottom: #8ea8c1;
  --wx-accent: rgba(255, 255, 255, 0.2);
}

.wx-bg--cloudy-night {
  --wx-bg-top: #1b2946;
  --wx-bg-bottom: #415d82;
  --wx-accent: rgba(203, 213, 225, 0.18);
}

.wx-bg--rain-day {
  --wx-bg-top: #334861;
  --wx-bg-bottom: #6b8cab;
  --wx-accent: rgba(125, 211, 252, 0.2);
}

.wx-bg--rain-night {
  --wx-bg-top: #0f1729;
  --wx-bg-bottom: #30445f;
  --wx-accent: rgba(125, 211, 252, 0.16);
}

.wx-bg--snow-day {
  --wx-bg-top: #6e86a3;
  --wx-bg-bottom: #c6d7ea;
  --wx-accent: rgba(255, 255, 255, 0.28);
}

.wx-bg--snow-night {
  --wx-bg-top: #1f2c42;
  --wx-bg-bottom: #576b87;
  --wx-accent: rgba(226, 232, 240, 0.18);
}

.wx-bg--thunder {
  --wx-bg-top: #111123;
  --wx-bg-bottom: #344069;
  --wx-accent: rgba(196, 181, 253, 0.22);
}

.wx-bg--fog {
  --wx-bg-top: #5e7898;
  --wx-bg-bottom: #bccddf;
  --wx-accent: rgba(255, 255, 255, 0.2);
}

.wx-panel::before,
.wx-dashboard::before {
  content: '';
  position: absolute;
  inset: auto -58px 52% auto;
  width: 188px;
  height: 188px;
  border-radius: 999px;
  background: radial-gradient(circle, var(--wx-accent) 0%, transparent 68%);
  filter: blur(2px);
  opacity: 0.92;
  pointer-events: none;
}

.wx-dashboard::before {
  inset: -28px -24px auto auto;
  width: 110px;
  height: 110px;
  filter: blur(1px);
  opacity: 0.28;
}

.wx-panel__veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.08), rgba(8, 15, 28, 0.24)),
    radial-gradient(circle at 18% 20%, rgba(255, 255, 255, 0.1), transparent 38%);
  pointer-events: none;
}

.wx-dashboard .wx-panel__veil {
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.02), rgba(8, 15, 28, 0.14)),
    radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.04), transparent 32%);
}

.wx-panel__veil--dashboard {
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.02), rgba(8, 15, 28, 0.12)),
    radial-gradient(circle at 16% 16%, rgba(255, 255, 255, 0.04), transparent 30%);
}

.wx-scene {
  position: absolute;
  inset: 54px 0 auto 0;
  height: 176px;
  pointer-events: none;
  overflow: hidden;
}

.wx-dashboard .wx-scene {
  inset: 10px 0 auto 0;
  height: 82px;
  opacity: 0.46;
}

.wx-scene__orb,
.wx-scene__cloud,
.wx-scene__spark,
.wx-scene__drop,
.wx-scene__flake,
.wx-scene__mist,
.wx-scene__flash {
  position: absolute;
  opacity: 0;
}

.wx-scene__orb {
  top: 6px;
  right: -10px;
  width: 100px;
  height: 100px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.56), rgba(255, 255, 255, 0.02) 68%);
  filter: blur(1px);
}

.wx-scene__cloud {
  width: 92px;
  height: 30px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.02));
  filter: blur(2px);
}

.wx-scene__cloud--1 {
  top: 28px;
  right: 42px;
}

.wx-scene__cloud--2 {
  top: 62px;
  right: 88px;
  width: 68px;
  height: 22px;
}

.wx-scene__spark {
  width: 3px;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
}

.wx-scene__spark--1 {
  top: 20px;
  right: 118px;
}

.wx-scene__spark--2 {
  top: 54px;
  right: 150px;
}

.wx-scene__spark--3 {
  top: 34px;
  right: 72px;
}

.wx-scene__drop {
  top: 42px;
  right: 78px;
  width: 2px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(186, 230, 253, 0.6));
}

.wx-scene__drop--2 {
  right: 96px;
  height: 11px;
}

.wx-scene__drop--3 {
  right: 114px;
  height: 16px;
}

.wx-scene__flake {
  top: 42px;
  right: 90px;
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
}

.wx-scene__flake--2 {
  top: 92px;
  right: 118px;
  width: 3px;
  height: 3px;
}

.wx-scene__mist {
  left: -15%;
  width: 140%;
  height: 34px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  filter: blur(14px);
}

.wx-scene__mist--1 {
  top: 40px;
}

.wx-scene__mist--2 {
  top: 78px;
}

.wx-scene__flash {
  inset: 0;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.08);
}

.wx-noise::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 148px 148px;
  opacity: 0.04;
  pointer-events: none;
}

.wx-dashboard.wx-noise::after {
  opacity: 0.016;
}

.wx-fade-slide-enter-active,
.wx-fade-slide-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
}

.wx-fade-slide-enter-from,
.wx-fade-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
`,`
.wx-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  border: none;
  background: transparent;
  color: rgb(71, 85, 105);
  border-radius: 999px;
  padding: 4px 8px;
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}

.wx-trigger:hover {
  background: rgba(15, 23, 42, 0.06);
  transform: none;
}

.wx-trigger__icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  height: auto;
  border-radius: 0;
  background: transparent;
}

.wx-trigger__icon {
  width: 16px;
  height: 16px;
  color: currentColor;
}

.wx-trigger__copy {
  display: none;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.05;
}

.wx-trigger__copy small {
  max-width: 88px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(100, 116, 139);
  font-size: 10px;
}

.wx-trigger__copy strong {
  font-size: 13px;
  font-weight: 700;
  color: rgb(30, 41, 59);
}

@media (min-width: 640px) {
  .wx-trigger__copy {
    display: flex;
  }
}
`,`
.wx-panel {
  width: min(360px, calc(100vw - 20px));
  border-radius: 24px;
  box-shadow: var(--wx-shadow);
  will-change: transform;
}

.wx-city-panel,
.wx-main-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  max-height: min(70vh, 520px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.18) transparent;
}

.wx-city-panel::-webkit-scrollbar,
.wx-main-panel::-webkit-scrollbar {
  width: 6px;
}

.wx-city-panel::-webkit-scrollbar-thumb,
.wx-main-panel::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.16);
  border-radius: 999px;
}

.wx-city-panel__head,
.wx-main-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.wx-city-panel__head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.wx-city-panel__summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--wx-outline);
  background: var(--wx-surface);
  backdrop-filter: blur(18px);
}

.wx-city-panel__label {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.08);
  color: var(--wx-text-primary);
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    transform 0.2s ease;
}

.wx-icon-btn:hover,
.wx-city-btn:hover,
.wx-locate-btn:hover,
.wx-action-btn:hover,
.wx-city-chip:hover {
  transform: translateY(-1px);
}

.wx-icon-btn:hover,
.wx-city-btn:hover,
.wx-locate-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  border-color: var(--wx-outline-strong);
}

.wx-icon-btn:disabled,
.wx-locate-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  transform: none;
}

.wx-search {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 15px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(16px);
}

.wx-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--wx-text-primary);
  font-size: 14px;
}

.wx-search input::placeholder {
  color: var(--wx-text-faint);
}

.wx-city-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wx-state-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--wx-text-secondary);
  font-size: 12px;
}

.wx-state-line--error {
  background: rgba(248, 113, 113, 0.12);
  color: #fecaca;
}

.wx-locate-btn,
.wx-action-btn,
.wx-city-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--wx-outline);
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    transform 0.2s ease;
}

.wx-locate-btn {
  justify-content: center;
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.1);
  color: var(--wx-text-primary);
  font-weight: 600;
}

.wx-action-btn {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 999px;
  background: #ffffff;
  border-color: rgba(148, 163, 184, 0.24);
  color: rgb(15, 23, 42);
}

.wx-action-btn:hover {
  background: rgb(248, 250, 252);
}

.wx-city-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wx-city-group h4 {
  margin: 0;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-city-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-city-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 46px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.1);
  color: var(--wx-text-primary);
  text-align: left;
  transition:
    transform 0.2s ease,
    background 0.2s ease,
    border-color 0.2s ease;
}

.wx-city-chip:hover {
  background: rgba(255, 255, 255, 0.16);
  border-color: var(--wx-outline);
}

.wx-city-chip__main {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  font-weight: 600;
}

.wx-city-chip__meta {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-city-btn {
  min-height: 34px;
  max-width: 100%;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: var(--wx-text-primary);
  min-width: 0;
}

.wx-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wx-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(7, 14, 28, 0.18);
  color: var(--wx-text-secondary);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.wx-hero {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 0 0;
}

.wx-hero__eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--wx-text-faint);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.wx-hero__body {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.wx-hero__copy {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.wx-hero__temp {
  font-size: 52px;
  line-height: 0.92;
  letter-spacing: -0.06em;
  font-weight: 200;
}

.wx-hero__text {
  font-size: 14px;
  font-weight: 700;
}

.wx-hero__sub {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 11px;
  color: var(--wx-text-secondary);
}

.wx-hero__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.wx-hero__icon-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(18px);
}

.wx-hero__icon {
  width: 46px;
  height: 46px;
  filter: drop-shadow(0 16px 22px rgba(8, 15, 30, 0.18));
}

.wx-hero__unit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(7, 14, 28, 0.18);
  color: var(--wx-text-secondary);
  font-size: 12px;
}

.wx-stale-badge {
  padding: 6px 9px;
  border-radius: 12px;
  border: 1px solid rgba(250, 204, 21, 0.24);
  background: rgba(250, 204, 21, 0.16);
  color: #fef3c7;
  font-size: 12px;
}

.wx-chip-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-chip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 60px;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.07));
  backdrop-filter: blur(18px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.wx-chip span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-chip strong {
  font-size: 15px;
  line-height: 1.1;
  font-weight: 700;
}

.wx-chip small {
  font-size: 10px;
  color: var(--wx-text-secondary);
}

.wx-hourly-band,
.wx-forecast-sheet {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0 0;
}

.wx-section-head--inline {
  padding: 0 4px;
}

.wx-hourly-scroll {
  gap: 12px;
  padding: 8px 0 6px;
}

.wx-hour-item {
  flex: 0 0 66px;
  padding: 12px 8px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.06));
  backdrop-filter: blur(18px);
}

.wx-hour-item--active {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.08));
}

.wx-sun-strip {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-sun-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(7, 14, 28, 0.16);
  backdrop-filter: blur(14px);
}

.wx-sun-chip span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-sun-chip strong {
  font-size: 13px;
  font-weight: 700;
}

.wx-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 22px;
  border: 1px solid var(--wx-outline);
  background: var(--wx-surface);
  backdrop-filter: blur(18px) saturate(1.2);
}

.wx-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.wx-section-head h4 {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
}

.wx-section-head span {
  font-size: 10px;
  color: var(--wx-text-faint);
}

.wx-hourly-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  scrollbar-width: none;
  padding-bottom: 2px;
}

.wx-hourly-scroll::-webkit-scrollbar {
  display: none;
}

.wx-hour-item {
  flex: 0 0 54px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 9px 6px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid transparent;
  color: var(--wx-text-secondary);
}

.wx-hour-item--active {
  background: rgba(255, 255, 255, 0.18);
  border-color: var(--wx-outline-strong);
  color: var(--wx-text-primary);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
}

.wx-hour-item__time {
  font-size: 10px;
}

.wx-hour-item__temp {
  font-size: 12px;
  font-weight: 700;
  color: var(--wx-text-primary);
}

.wx-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.wx-metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 90px;
  padding: 14px 14px 12px;
  border-radius: 20px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.09);
  backdrop-filter: blur(16px);
}

.wx-metric span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-metric strong {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
}

.wx-metric small {
  font-size: 12px;
  color: var(--wx-text-secondary);
}

.wx-forecast {
  gap: 10px;
}

.wx-forecast-row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) auto minmax(0, 0.9fr);
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.wx-forecast-row:first-of-type {
  padding-top: 0;
  border-top: none;
}

.wx-forecast-row__day {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.wx-forecast-row__day span {
  font-size: 12px;
  font-weight: 600;
}

.wx-forecast-row__day small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
  color: var(--wx-text-faint);
}

.wx-forecast-row__temp {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  font-size: 10px;
  color: var(--wx-text-secondary);
}

.wx-forecast-row__temp span:first-child {
  color: var(--wx-text-primary);
  font-weight: 600;
}

.wx-forecast-row__temp span:last-child {
  color: var(--wx-text-secondary);
}
`,`
.wx-skeleton-wrap,
.wx-dashboard-skeleton {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.wx-dashboard-skeleton__row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.wx-skeleton {
  border-radius: 18px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.08) 20%,
    rgba(255, 255, 255, 0.18) 50%,
    rgba(255, 255, 255, 0.08) 80%
  );
  background-size: 200% 100%;
  animation: wx-shimmer 1.6s linear infinite;
}

.wx-skeleton--lg {
  min-height: 136px;
}

.wx-skeleton--md {
  min-height: 72px;
}

.wx-skeleton--grid {
  min-height: 160px;
}

.wx-skeleton--tile {
  min-height: 88px;
}

@keyframes wx-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.wx-empty,
.wx-dashboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 260px;
  padding: 20px;
  border-radius: 22px;
  border: 1px dashed rgba(148, 163, 184, 0.24);
  background: rgba(248, 250, 252, 0.68);
  text-align: center;
}

.wx-empty p,
.wx-dashboard-empty__desc {
  margin: 0;
  font-size: 12px;
  color: rgb(100, 116, 139);
}

.wx-dashboard-empty__title {
  font-size: 14px;
  font-weight: 700;
  color: rgb(15, 23, 42);
}
`,`
.wx-dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.wx-dashboard {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: auto;
  min-height: 0;
  padding: 12px;
  border-radius: 18px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.14);
}

.wx-dashboard__topbar,
.wx-dashboard__hero,
.wx-dashboard__chip-row,
.wx-dashboard__forecast-ribbon {
  position: relative;
  z-index: 1;
}

.wx-dashboard__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.wx-dashboard__topbar .wx-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(6px);
}

.wx-dashboard__hero {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.wx-dashboard__eyebrow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  min-width: 0;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-dashboard__eyebrow span:first-child {
  max-width: min(100%, 180px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--wx-text-primary);
}

.wx-dashboard__eyebrow span:last-child {
  color: var(--wx-text-secondary);
}

.wx-dashboard__hero-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  min-width: 0;
}

.wx-dashboard__temp {
  font-size: 46px;
  line-height: 0.86;
  letter-spacing: -0.05em;
  font-weight: 220;
  flex-shrink: 0;
}

.wx-dashboard__condition-wrap {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 5px;
  min-width: 0;
  padding-bottom: 2px;
}

.wx-dashboard__condition-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.wx-dashboard__condition {
  font-size: 14px;
  line-height: 1.2;
  font-weight: 700;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 10px;
  font-size: 11px;
  line-height: 1.25;
  color: var(--wx-text-secondary);
}

.wx-dashboard__meta span {
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(6px);
  flex-shrink: 0;
}

.wx-dashboard__icon {
  width: 18px;
  height: 18px;
}

.wx-dashboard__chip-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-dashboard__chip {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  min-height: 50px;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
}

.wx-dashboard__chip span {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-dashboard__chip strong {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__chip small {
  font-size: 10px;
  line-height: 1.2;
  color: var(--wx-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__chip--wide {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'label value'
    'note value';
  align-items: center;
  gap: 10px;
  min-height: 50px;
}

.wx-dashboard__chip--wide span {
  grid-area: label;
}

.wx-dashboard__chip--wide strong {
  grid-area: value;
  font-size: 18px;
}

.wx-dashboard__chip--wide small {
  grid-area: note;
}

.wx-dashboard__forecast-ribbon {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.wx-dashboard__forecast-pill {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  min-width: 0;
  padding: 7px 9px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(7, 14, 28, 0.1);
  backdrop-filter: blur(6px);
}

.wx-dashboard__forecast-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  font-size: 10px;
  font-weight: 700;
}

.wx-dashboard__forecast-text {
  min-height: 0;
  font-size: 10px;
  line-height: 1.2;
  color: var(--wx-text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__forecast-range {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
}

.wx-dashboard__forecast-range span:first-child {
  font-weight: 700;
}

.wx-dashboard__forecast-range span:last-child {
  color: var(--wx-text-secondary);
}
`,`
.wx-scene--sun .wx-scene__orb,
.wx-scene--moon-star .wx-scene__orb,
.wx-scene--cloud .wx-scene__cloud,
.wx-scene--rain .wx-scene__cloud,
.wx-scene--snow .wx-scene__cloud,
.wx-scene--moon-star .wx-scene__spark,
.wx-scene--rain .wx-scene__drop,
.wx-scene--snow .wx-scene__flake,
.wx-scene--fog .wx-scene__mist,
.wx-scene--thunder .wx-scene__flash {
  opacity: 1;
}

.wx-scene--sun .wx-scene__orb {
  background: radial-gradient(circle, rgba(253, 224, 71, 0.8), rgba(251, 191, 36, 0.08) 70%);
  box-shadow: 0 0 80px rgba(253, 224, 71, 0.22);
  animation: wx-sun-pulse 7s ease-in-out infinite;
}

.wx-scene--moon-star .wx-scene__orb {
  width: 108px;
  height: 108px;
  background: radial-gradient(circle, rgba(226, 232, 240, 0.5), rgba(226, 232, 240, 0.04) 70%);
  box-shadow: 0 0 60px rgba(226, 232, 240, 0.12);
}

.wx-scene--cloud .wx-scene__cloud,
.wx-scene--rain .wx-scene__cloud,
.wx-scene--snow .wx-scene__cloud {
  animation: wx-cloud-float 12s ease-in-out infinite;
}

.wx-scene--moon-star .wx-scene__spark {
  animation: wx-sparkle 2.8s ease-in-out infinite;
}

.wx-scene--rain .wx-scene__drop {
  animation: wx-rain-fall 1.6s linear infinite;
}

.wx-scene--snow .wx-scene__flake {
  animation: wx-snow-drift 3.6s ease-in-out infinite;
}

.wx-scene--fog .wx-scene__mist {
  animation: wx-mist-drift 14s ease-in-out infinite;
}

.wx-scene--thunder .wx-scene__flash {
  animation: wx-thunder-flash 4.8s ease-in-out infinite;
}

@keyframes wx-sun-pulse {
  0%,
  100% {
    transform: scale(0.96);
    opacity: 0.76;
  }
  50% {
    transform: scale(1.06);
    opacity: 1;
  }
}

@keyframes wx-cloud-float {
  0%,
  100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(8px) translateY(-4px);
  }
}

@keyframes wx-sparkle {
  0%,
  100% {
    transform: scale(0.8);
    opacity: 0.18;
  }
  50% {
    transform: scale(1.25);
    opacity: 1;
  }
}

@keyframes wx-rain-fall {
  0% {
    transform: translateY(-6px);
    opacity: 0;
  }
  25% {
    opacity: 0.85;
  }
  100% {
    transform: translateY(40px);
    opacity: 0;
  }
}

@keyframes wx-snow-drift {
  0% {
    transform: translateY(-4px) translateX(0) scale(0.8);
    opacity: 0;
  }
  30% {
    opacity: 0.92;
  }
  100% {
    transform: translateY(38px) translateX(10px) scale(1.05);
    opacity: 0;
  }
}

@keyframes wx-mist-drift {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(24px);
  }
}

@keyframes wx-thunder-flash {
  0%,
  90%,
  100% {
    opacity: 0;
  }
  92% {
    opacity: 0.75;
  }
  94% {
    opacity: 0.1;
  }
  96% {
    opacity: 0.35;
  }
}
`,`
@media (max-width: 480px) {
  .wx-city-grid {
    grid-template-columns: 1fr;
  }

  .wx-city-panel,
  .wx-main-panel,
  .wx-dashboard {
    padding: 10px;
  }

  .wx-hero__body {
    flex-direction: column;
    align-items: flex-start;
  }

  .wx-hero__meta {
    align-items: flex-end;
  }

  .wx-hero__temp,
  .wx-dashboard__temp {
    font-size: 40px;
  }

  .wx-dashboard {
    gap: 9px;
    border-radius: 16px;
  }

  .wx-dashboard__topbar {
    gap: 8px;
  }

  .wx-dashboard__eyebrow span:first-child {
    max-width: 132px;
  }

  .wx-dashboard__hero {
    gap: 0;
  }

  .wx-dashboard__hero-main {
    gap: 8px;
  }

  .wx-dashboard__condition-line {
    gap: 6px;
  }

  .wx-dashboard__condition {
    font-size: 14px;
  }

  .wx-dashboard__chip-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wx-dashboard__chip--wide {
    grid-column: 1 / -1;
  }

  .wx-chip-grid,
  .wx-sun-strip {
    grid-template-columns: 1fr;
  }

  .wx-dashboard__forecast-ribbon {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 5px;
  }

  .wx-dashboard__forecast-pill {
    padding: 7px 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .wx-panel *,
  .wx-dashboard *,
  .wx-trigger {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}
`].join(`
`);function On(){const n=window.NovusPluginShared;if(n!=null&&n.registerLocale&&(n.registerLocale("zh-CN","plugin.weather-widget",Se),n.registerLocale("zh","plugin.weather-widget",Se),n.registerLocale("en-US","plugin.weather-widget",We),n.registerLocale("en","plugin.weather-widget",We)),!document.getElementById("wx-plugin-styles")){const o=document.createElement("style");o.id="wx-plugin-styles",o.textContent=Un,document.head.appendChild(o)}}k.WeatherDashboardWidget=Dt,k.WeatherHeaderWidget=Pn,k.setup=On,Object.defineProperty(k,Symbol.toStringTag,{value:"Module"})}));
