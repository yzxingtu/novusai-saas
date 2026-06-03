(function(E,e){typeof exports=="object"&&typeof module<"u"?e(exports,require("vue"),require("@novus/plugin-shared"),require("ant-design-vue")):typeof define=="function"&&define.amd?define(["exports","vue","@novus/plugin-shared","ant-design-vue"],e):(E=typeof globalThis<"u"?globalThis:E||self,e(E.NovusPlugin_weather_widget={},E.Vue,E.NovusPluginShared,E.AntDesignVue))})(this,(function(E,e,t,He){"use strict";const Ye=[{name:"北京",latitude:39.9042,longitude:116.4074,country:"China"},{name:"上海",latitude:31.2304,longitude:121.4737,country:"China"},{name:"广州",latitude:23.1291,longitude:113.2644,country:"China"},{name:"深圳",latitude:22.5431,longitude:114.0579,country:"China"},{name:"杭州",latitude:30.2741,longitude:120.1551,country:"China"},{name:"成都",latitude:30.5728,longitude:104.0668,country:"China"},{name:"武汉",latitude:30.5928,longitude:114.3055,country:"China"},{name:"南京",latitude:32.0603,longitude:118.7969,country:"China"},{name:"重庆",latitude:29.4316,longitude:106.9123,country:"China"},{name:"西安",latitude:34.3416,longitude:108.9398,country:"China"},{name:"苏州",latitude:31.299,longitude:120.5853,country:"China"},{name:"天津",latitude:39.3434,longitude:117.3616,country:"China"}],pe="novusai_weather_config",xe="novusai_weather_data",Qe=6,Ge=600,M={city:"Shanghai",latitude:31.2304,longitude:121.4737,recentCities:[{name:"Shanghai",latitude:31.2304,longitude:121.4737,country:"China"}]},J=e.ref(!1);function we(n,r,l){return Math.max(r,Math.min(l,n))}function S(){return`${window.location.pathname.startsWith("/admin")?"/admin":"/tenant"}/plugins/weather-widget/api`}function Ke(n){return n==="fahrenheit"?"fahrenheit":"celsius"}function Je(){try{const n=localStorage.getItem(pe);if(J.value=!!n,n){const r=JSON.parse(n);return{city:r.city||M.city,latitude:r.latitude??M.latitude,longitude:r.longitude??M.longitude,recentCities:Array.isArray(r.recentCities)&&r.recentCities.length>0?r.recentCities:M.recentCities}}}catch{J.value=!1}return{...M,recentCities:[...M.recentCities]}}function te(n){try{localStorage.setItem(pe,JSON.stringify(n)),J.value=!0}catch{}}function ge(){try{const n=localStorage.getItem(xe);if(n)return JSON.parse(n)}catch{}return null}function Ze(n){try{localStorage.setItem(xe,JSON.stringify(n))}catch{}}const m=e.ref(Je()),B=e.ref({}),P=e.ref(null),X=e.ref([]),j=e.ref([]),H=e.ref(null),ne=e.ref(!1),ae=e.ref(!0),oe=e.ref(null),re=e.ref(!1),Y=e.ref(null),fe=e.ref(!1),ie=e.ref(!1),U=e.ref(null);let C=null,Q=0,he=!1,Z=0,A=null,W=null;function ue(n,r){if(!n){ie.value=!1;return}ie.value=Date.now()-n>r}function ve(n,r,l){A&&(clearInterval(A),A=null),!(!r||Q<=0)&&(A=setInterval(()=>{l()},n))}function et(){const n=e.computed(()=>m.value.city),r=e.computed(()=>m.value.recentCities),l=e.computed(()=>Ke(B.value.temperature_unit)),s=e.computed(()=>we(B.value.forecast_days??3,1,7)),N=e.computed(()=>we(B.value.cache_ttl??Ge,60,3600)*1e3),$=e.computed(()=>Math.max(N.value,300*1e3));async function R(){try{const o=await t.requestClient.get(`${S()}/config`);o!=null&&o.config&&(B.value=o.config)}catch{B.value={}}}async function D(){var g;const o=(g=B.value.default_city)==null?void 0:g.trim();if(!o||J.value)return;const w=await O(o);if(w.length>0){const f=w[0];m.value.city=f.name,m.value.latitude=f.latitude,m.value.longitude=f.longitude,m.value.recentCities=[f],te(m.value);return}m.value.city=o,te(m.value)}async function V(){const o=++Z;W&&W.abort(),W=new AbortController,ne.value=!0,oe.value=null;const{latitude:w,longitude:g}=m.value,f=s.value;try{const[_,b,x,d]=await Promise.all([t.requestClient.get(`${S()}/current`,{params:{lat:w,lon:g},signal:W.signal}),t.requestClient.get(`${S()}/forecast`,{params:{lat:w,lon:g,days:f},signal:W.signal}).catch(()=>null),t.requestClient.get(`${S()}/hourly`,{params:{lat:w,lon:g},signal:W.signal}).catch(()=>null),t.requestClient.get(`${S()}/air-quality`,{params:{lat:w,lon:g},signal:W.signal}).catch(()=>null)]);if(o!==Z)return;P.value=(_==null?void 0:_.weather)??null,X.value=((b==null?void 0:b.forecast)??[]).slice(0,f),j.value=(x==null?void 0:x.hourly)??[],H.value=(d==null?void 0:d.air_quality)??null,U.value=Date.now(),ue(U.value,$.value),Ze({current:P.value,forecast:X.value,hourly:j.value,airQuality:H.value,timestamp:U.value})}catch(_){if(o!==Z)return;const b=_ instanceof Error?_.message:String(_);if(b.toLowerCase().includes("aborted"))return;oe.value=b;const x=ge();x!=null&&x.current&&(P.value=x.current,X.value=x.forecast.slice(0,f),j.value=x.hourly,H.value=x.airQuality,U.value=x.timestamp,ue(x.timestamp,$.value))}finally{o===Z&&(ne.value=!1,ae.value=!1)}}async function O(o){const w=o.trim();if(!w)return[];try{const g=await t.requestClient.get(`${S()}/geocoding`,{params:{name:w,count:8}});return(g==null?void 0:g.cities)??[]}catch{return[]}}async function h(o){m.value.city=o.name,m.value.latitude=o.latitude,m.value.longitude=o.longitude;const w=m.value.recentCities.filter(g=>!(Math.abs(g.latitude-o.latitude)<.01&&Math.abs(g.longitude-o.longitude)<.01));w.unshift(o),m.value.recentCities=w.slice(0,Qe),te(m.value),fe.value=!1,await V()}async function z(){var o,w;if(!navigator.geolocation){Y.value="locate_failed";return}re.value=!0,Y.value=null;try{const g=await new Promise((x,d)=>{navigator.geolocation.getCurrentPosition(x,d,{enableHighAccuracy:!0,timeout:1e4,maximumAge:3e5})}),{latitude:f,longitude:_}=g.coords;let b=null;for(let x=0;x<2;x+=1){try{const d=await t.requestClient.get(`${S()}/geocoding`,{params:{lat:f,lon:_}});if((o=d==null?void 0:d.cities)!=null&&o.length&&((w=d.cities[0])!=null&&w.name)){b=d.cities[0];break}}catch{}x===0&&await new Promise(d=>setTimeout(d,500))}b?await h(b):(await h({name:`${f.toFixed(2)}, ${_.toFixed(2)}`,latitude:f,longitude:_}),Y.value="locate_fallback")}catch{Y.value="locate_failed"}finally{re.value=!1}}async function I(){if(Q+=1,!he){he=!0;const o=ge();o!=null&&o.current&&(P.value=o.current,X.value=o.forecast,j.value=o.hourly,H.value=o.airQuality,U.value=o.timestamp,ae.value=!1),await R(),await D(),await V()}ve(N.value,B.value.auto_refresh??!0,V)}function F(){Q=Math.max(0,Q-1),Q<=0&&A&&(clearInterval(A),A=null)}return{cityName:n,recentCities:r,current:P,forecast:X,hourly:j,airQuality:H,loading:ne,initialLoading:ae,error:oe,locating:re,locateError:Y,showCitySelector:fe,isStale:ie,pluginConfig:B,temperatureUnit:l,forecastDays:s,lastUpdatedAt:U,fetchAll:V,searchCity:O,selectCity:h,geolocate:z,mount:I,unmount:F}}function me(){return C||(C=et()),e.onMounted(()=>{C==null||C.mount()}),e.onBeforeUnmount(()=>{C==null||C.unmount()}),C}function _e(n,r){return r?n.weather_text_zh||n.weather_text_en||"--":n.weather_text_en||n.weather_text_zh||"--"}function tt(n,r){return n==null||Number.isNaN(n)?null:r==="fahrenheit"?n*9/5+32:n}function k(n,r,l=0){const s=tt(n,r);return s==null?"--":s.toFixed(l)}function nt(n){return n==="fahrenheit"?"F":"C"}function be(n,r,l=1){return n==null||Number.isNaN(n)?"--":(r==="fahrenheit"?n*.621371:n).toFixed(l)}function ye(n){return[n.admin1,n.country].filter(Boolean).join(" · ")}function ke(n,r){return n?new Intl.DateTimeFormat(r,{hour:"2-digit",minute:"2-digit"}).format(n):"--:--"}function Ee(n){if(!n)return"--:--";const r=n.includes("T")?n.split("T")[1]:n;return r?r.slice(0,5):"--:--"}function Ne(n){return n==null?"na":n<=50?"good":n<=100?"moderate":n<=150?"unhealthy_sensitive":n<=200?"unhealthy":n<=300?"very_unhealthy":"hazardous"}function Ve(n){return n==null?"#A7B3CC":n<=50?"#47D16D":n<=100?"#EABD43":n<=150?"#F49D58":n<=200?"#F06B67":n<=300?"#A47DE8":"#D45A8A"}function Ce(n,r,l){if(r===0)return l("plugin.weather-widget.ui.today");if(r===1)return l("plugin.weather-widget.ui.tomorrow");if(r===2)return l("plugin.weather-widget.ui.day_after");const s=new Date(n).getDay();return l(`plugin.weather-widget.ui.weekday_${s}`)}const $e={0:{icon:"sun",nightIcon:"moon",scene:"clear"},1:{icon:"sun",nightIcon:"moon",scene:"clear"},2:{icon:"cloud-sun",nightIcon:"cloud-moon",scene:"cloudy"},3:{icon:"cloud",scene:"cloudy"},45:{icon:"cloud-fog",scene:"fog"},48:{icon:"cloud-fog",scene:"fog"},51:{icon:"cloud-drizzle",scene:"drizzle"},53:{icon:"cloud-drizzle",scene:"drizzle"},55:{icon:"cloud-drizzle",scene:"drizzle"},56:{icon:"cloud-drizzle",scene:"drizzle"},57:{icon:"cloud-drizzle",scene:"drizzle"},61:{icon:"cloud-rain",scene:"rain"},63:{icon:"cloud-rain",scene:"rain"},65:{icon:"cloud-rain",scene:"rain"},66:{icon:"cloud-rain",scene:"rain"},67:{icon:"cloud-rain",scene:"rain"},71:{icon:"snowflake",scene:"snow"},73:{icon:"snowflake",scene:"snow"},75:{icon:"snowflake",scene:"snow"},77:{icon:"snowflake",scene:"snow"},80:{icon:"cloud-rain",scene:"rain"},81:{icon:"cloud-rain",scene:"rain"},82:{icon:"cloud-rain",scene:"rain"},85:{icon:"snowflake",scene:"snow"},86:{icon:"snowflake",scene:"snow"},95:{icon:"cloud-lightning",scene:"thunderstorm"},96:{icon:"cloud-lightning",scene:"thunderstorm"},99:{icon:"cloud-lightning",scene:"thunderstorm"}},ze={icon:"cloud",scene:"cloudy"};function Be(n,r=!0){const l=$e[n]??ze;return{icon:!r&&l.nightIcon?l.nightIcon:l.icon,scene:l.scene}}const at={"clear-day":{bgClass:"wx-bg--clear-day",scene:"sun"},"clear-night":{bgClass:"wx-bg--clear-night",scene:"moon-star"},"cloudy-day":{bgClass:"wx-bg--cloudy-day",scene:"cloud"},"cloudy-night":{bgClass:"wx-bg--cloudy-night",scene:"cloud"},"fog-day":{bgClass:"wx-bg--fog",scene:"fog"},"fog-night":{bgClass:"wx-bg--fog",scene:"fog"},"drizzle-day":{bgClass:"wx-bg--rain-day",scene:"rain"},"drizzle-night":{bgClass:"wx-bg--rain-night",scene:"rain"},"rain-day":{bgClass:"wx-bg--rain-day",scene:"rain"},"rain-night":{bgClass:"wx-bg--rain-night",scene:"rain"},"snow-day":{bgClass:"wx-bg--snow-day",scene:"snow"},"snow-night":{bgClass:"wx-bg--snow-night",scene:"snow"},"thunderstorm-day":{bgClass:"wx-bg--thunder",scene:"thunder"},"thunderstorm-night":{bgClass:"wx-bg--thunder",scene:"thunder"}};function De(n,r=!0){const l=$e[n]??ze,s=r?"day":"night",N=`${l.scene}-${s}`;return at[N]??{bgClass:"wx-bg--cloudy-day",scene:"cloud"}}const ot={class:"wx-dashboard-shell"},rt={class:"wx-dashboard__topbar"},it={class:"wx-dashboard__eyebrow"},lt=["disabled","aria-label"],st={class:"wx-dashboard__hero"},ct={class:"wx-dashboard__hero-main"},dt={class:"wx-dashboard__temp"},pt={class:"wx-dashboard__condition-wrap"},xt={class:"wx-dashboard__condition-line"},wt={class:"wx-dashboard__icon-wrap"},gt={class:"wx-dashboard__condition"},ft={class:"wx-dashboard__meta"},ht={class:"wx-dashboard__chip-row"},ut={key:0,class:"wx-dashboard__forecast-ribbon"},mt={class:"wx-dashboard__forecast-head"},_t={class:"wx-dashboard__forecast-range"},bt={class:"wx-dashboard__forecast-text"},yt={key:1,class:"wx-dashboard-skeleton"},kt={key:2,class:"wx-dashboard-empty"},Et={class:"wx-dashboard-empty__title"},Nt={key:0,class:"wx-dashboard-empty__desc"},Vt=e.defineComponent({__name:"WeatherDashboardWidget",setup(n){const{cityName:r,current:l,forecast:s,airQuality:N,loading:$,initialLoading:R,error:D,isStale:V,lastUpdatedAt:O,temperatureUnit:h,fetchAll:z}=me(),I=e.computed(()=>t.$t("plugin.weather-widget._meta.lang")==="zh"),F=e.computed(()=>s.value.slice(0,3)),o=e.computed(()=>l.value?De(l.value.weather_code,l.value.is_day):{bgClass:"wx-bg--cloudy-day",scene:"cloud"}),w=e.computed(()=>ke(O.value,I.value?"zh-CN":"en-US")),g=e.computed(()=>V.value?t.$t("plugin.weather-widget.ui.cached_data"):t.$t("plugin.weather-widget.ui.live_data")),f=e.computed(()=>h.value==="fahrenheit"?t.$t("plugin.weather-widget.ui.unit_mph"):t.$t("plugin.weather-widget.ui.unit_kmh")),_=e.computed(()=>{var d,u,p;return l.value?[{key:"humidity",label:t.$t("plugin.weather-widget.ui.humidity"),note:void 0,tone:void 0,value:`${l.value.humidity??"--"}%`,wide:!1},{key:"wind",label:t.$t("plugin.weather-widget.ui.wind_speed"),note:void 0,tone:void 0,value:`${be(l.value.wind_speed,h.value)} ${f.value}`,wide:!1},{key:"aqi",label:t.$t("plugin.weather-widget.ui.aqi"),value:`${((d=N.value)==null?void 0:d.aqi)??"--"}`,note:t.$t(`plugin.weather-widget.aqi_level.${Ne((u=N.value)==null?void 0:u.aqi)}`),tone:Ve((p=N.value)==null?void 0:p.aqi),wide:!0}]:[]});function b(d){return _e(d,I.value)}function x(d,u=!0){return Be(d,u).icon}return(d,u)=>(e.openBlock(),e.createElementBlock("div",ot,[e.unref(l)?(e.openBlock(),e.createElementBlock("section",{key:0,class:e.normalizeClass(["wx-dashboard wx-noise",[o.value.bgClass,`wx-scene--${o.value.scene}`]])},[u[2]||(u[2]=e.createStaticVNode('<div class="wx-panel__veil wx-panel__veil--dashboard"></div><div class="wx-scene wx-scene--dashboard" aria-hidden="true"><span class="wx-scene__orb"></span><span class="wx-scene__cloud wx-scene__cloud--1"></span><span class="wx-scene__cloud wx-scene__cloud--2"></span><span class="wx-scene__spark wx-scene__spark--1"></span><span class="wx-scene__spark wx-scene__spark--2"></span><span class="wx-scene__drop wx-scene__drop--1"></span><span class="wx-scene__drop wx-scene__drop--2"></span><span class="wx-scene__flake wx-scene__flake--1"></span><span class="wx-scene__mist wx-scene__mist--1"></span><span class="wx-scene__flash"></span></div>',2)),e.createElementVNode("div",rt,[e.createElementVNode("div",it,[e.createElementVNode("span",null,e.toDisplayString(e.unref(r)),1),e.createElementVNode("span",null,e.toDisplayString(g.value),1)]),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref($),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.refresh"),onClick:u[0]||(u[0]=(...p)=>e.unref(z)&&e.unref(z)(...p))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref($)?"lucide:loader-2":"lucide:refresh-cw",class:e.normalizeClass(e.unref($)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,lt)]),e.createElementVNode("div",st,[e.createElementVNode("div",ct,[e.createElementVNode("div",dt,e.toDisplayString(e.unref(k)(e.unref(l).temperature,e.unref(h)))+"° ",1),e.createElementVNode("div",pt,[e.createElementVNode("div",xt,[e.createElementVNode("div",wt,[e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${x(e.unref(l).weather_code,e.unref(l).is_day)}`,class:"wx-dashboard__icon"},null,8,["icon"])]),e.createElementVNode("div",gt,e.toDisplayString(b(e.unref(l))),1)]),e.createElementVNode("div",ft,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.feels_like"))+" "+e.toDisplayString(e.unref(k)(e.unref(l).apparent_temperature,e.unref(h)))+"° ",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.last_updated"))+" "+e.toDisplayString(w.value),1)])])])]),e.createElementVNode("div",ht,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(_.value,p=>(e.openBlock(),e.createElementBlock("article",{key:p.key,class:e.normalizeClass(["wx-dashboard__chip",p.wide?"wx-dashboard__chip--wide":""])},[e.createElementVNode("span",null,e.toDisplayString(p.label),1),e.createElementVNode("strong",{style:e.normalizeStyle(p.tone?{color:p.tone}:void 0)},e.toDisplayString(p.value),5),p.note?(e.openBlock(),e.createElementBlock("small",{key:0,style:e.normalizeStyle(p.tone?{color:p.tone}:void 0)},e.toDisplayString(p.note),5)):e.createCommentVNode("",!0)],2))),128))]),F.value.length>0?(e.openBlock(),e.createElementBlock("div",ut,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(F.value,(p,q)=>(e.openBlock(),e.createElementBlock("article",{key:p.date,class:"wx-dashboard__forecast-pill"},[e.createElementVNode("div",mt,[e.createElementVNode("span",null,e.toDisplayString(e.unref(Ce)(p.date,q,e.unref(t.$t))),1),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${x(p.weather_code,!0)}`,class:"size-4"},null,8,["icon"])]),e.createElementVNode("div",_t,[e.createElementVNode("span",null,e.toDisplayString(e.unref(k)(p.temp_max,e.unref(h)))+"°",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(k)(p.temp_min,e.unref(h)))+"°",1)]),e.createElementVNode("div",bt,e.toDisplayString(b(p)),1)]))),128))])):e.createCommentVNode("",!0)],2)):e.unref(R)?(e.openBlock(),e.createElementBlock("div",yt,[...u[3]||(u[3]=[e.createStaticVNode('<div class="wx-skeleton wx-skeleton--lg"></div><div class="wx-dashboard-skeleton__row"><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div></div><div class="wx-dashboard-skeleton__row"><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div><div class="wx-skeleton wx-skeleton--tile"></div></div>',3)])])):(e.openBlock(),e.createElementBlock("div",kt,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:cloud-off",class:"size-10 text-muted-foreground"}),e.createElementVNode("div",Et,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.error")),1),e.unref(D)?(e.openBlock(),e.createElementBlock("div",Nt,e.toDisplayString(e.unref(D)),1)):e.createCommentVNode("",!0),e.createElementVNode("button",{type:"button",class:"wx-action-btn",onClick:u[1]||(u[1]=(...p)=>e.unref(z)&&e.unref(z)(...p))},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:refresh-cw",class:"size-4"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.retry")),1)])]))]))}}),Ct=["aria-label","aria-expanded"],$t={class:"wx-trigger__icon-wrap"},zt={class:"wx-trigger__copy"},Bt={key:"city-selector",class:"wx-city-panel"},Dt={class:"wx-city-panel__head"},It=["aria-label"],Tt=["aria-label"],Lt={class:"wx-city-panel__summary"},St={class:"wx-city-panel__label"},At={class:"wx-search"},Wt=["value","placeholder"],Rt={class:"wx-city-list"},Ft={key:0},qt={key:0,class:"wx-state-line"},Mt=["onClick"],Ut={class:"wx-city-chip__main"},Ot={class:"truncate"},Pt={key:0,class:"wx-city-chip__meta"},Xt={key:1,class:"wx-state-line"},jt=["disabled","aria-label"],Ht={key:1,class:"wx-state-line wx-state-line--error"},Yt={key:2,class:"wx-city-group"},Qt={class:"wx-city-grid"},Gt=["onClick"],Kt={class:"truncate"},Jt={class:"wx-city-group"},Zt={class:"wx-city-grid"},vt=["onClick"],en={class:"truncate"},tn={key:"weather-main",class:"wx-main-panel"},nn={key:0,class:"wx-skeleton-wrap"},an={key:1,class:"wx-empty"},on={class:"wx-main-head"},rn=["aria-label"],ln={class:"truncate"},sn={class:"wx-head-actions"},cn={class:"wx-status-chip"},dn=["disabled","aria-label"],pn=["disabled","aria-label"],xn={class:"wx-hero"},wn={class:"wx-hero__eyebrow"},gn={class:"wx-hero__body"},fn={class:"wx-hero__copy"},hn={class:"wx-hero__temp"},un={class:"wx-hero__text"},mn={class:"wx-hero__sub"},_n={key:0},bn={class:"wx-hero__meta"},yn={class:"wx-hero__icon-shell"},kn={class:"wx-hero__unit"},En={key:0,class:"wx-stale-badge"},Nn={class:"wx-chip-grid"},Vn={key:0,class:"wx-hourly-band"},Cn={class:"wx-section-head wx-section-head--inline"},$n={class:"wx-hour-item__time"},zn={class:"wx-hour-item__temp"},Bn={class:"wx-sun-strip"},Dn={class:"wx-sun-chip"},In={class:"wx-sun-chip"},Tn={key:1,class:"wx-forecast-sheet"},Ln={class:"wx-section-head wx-section-head--inline"},Sn={class:"wx-forecast-row__day"},An={class:"wx-forecast-row__temp"},Wn=e.defineComponent({__name:"WeatherHeaderWidget",setup(n){const{cityName:r,recentCities:l,current:s,forecast:N,hourly:$,airQuality:R,loading:D,initialLoading:V,error:O,locating:h,locateError:z,showCitySelector:I,isStale:F,temperatureUnit:o,forecastDays:w,lastUpdatedAt:g,fetchAll:f,searchCity:_,selectCity:b,geolocate:x}=me(),d=e.ref(!1),u=e.ref(""),p=e.ref([]),q=e.ref(!1),Le=e.ref(null),le=e.ref(null),se=e.ref(null),Se=e.ref({});let G=null,v=null;const Ae=e.computed(()=>t.$t("plugin.weather-widget._meta.lang")==="zh"),We=e.computed(()=>nt(o.value)),qn=e.computed(()=>o.value==="fahrenheit"?t.$t("plugin.weather-widget.ui.unit_mph"):t.$t("plugin.weather-widget.ui.unit_kmh")),K=e.computed(()=>N.value[0]??null),Re=e.computed(()=>N.value.slice(0,Math.min(w.value,3))),Fe=e.computed(()=>$.value.slice(0,6)),qe=e.computed(()=>F.value?t.$t("plugin.weather-widget.ui.cached_data"):t.$t("plugin.weather-widget.ui.live_data")),Mn=e.computed(()=>ke(g.value,Ae.value?"zh-CN":"en-US")),Me=e.computed(()=>s.value?De(s.value.weather_code,s.value.is_day):{bgClass:"wx-bg--cloudy-day",scene:"cloud"}),Un=e.computed(()=>{var c,i,y;return s.value?[{key:"humidity",label:t.$t("plugin.weather-widget.ui.humidity"),note:void 0,tone:void 0,value:`${s.value.humidity??"--"}%`},{key:"wind",label:t.$t("plugin.weather-widget.ui.wind_speed"),note:void 0,tone:void 0,value:`${be(s.value.wind_speed,o.value)} ${qn.value}`},{key:"uv",label:t.$t("plugin.weather-widget.ui.uv_index"),note:void 0,tone:void 0,value:`${s.value.uv_index??"--"}`},{key:"aqi",label:t.$t("plugin.weather-widget.ui.aqi"),value:`${((c=R.value)==null?void 0:c.aqi)??"--"}`,note:Pn((i=R.value)==null?void 0:i.aqi),tone:Ve((y=R.value)==null?void 0:y.aqi)}]:[]});function ee(c,i=!0){return Be(c,i).icon}function Ue(c){return _e(c,Ae.value)}function On(c,i){return i?t.$t("plugin.weather-widget.ui.now"):c}function Pn(c){const i=Ne(c);return t.$t(`plugin.weather-widget.aqi_level.${i}`)}function Xn(){return Math.max(Math.min(360,window.innerWidth-20),0)}function jn(){var je;const c=le.value;if(!c||!c.isConnected){d.value=!1;return}const i=4,y=10,T=c.getBoundingClientRect(),a=((je=se.value)==null?void 0:je.offsetWidth)??Xn(),L=Math.max(window.innerWidth-a-y,y),Gn=Math.min(Math.max(T.right-a,y),L);Se.value={left:`${Gn}px`,top:`${Math.max(T.bottom+i,y)}px`}}function Oe(c){var y,T;if(!d.value)return;const i=c.target;i&&((y=le.value)!=null&&y.contains(i)||(T=se.value)!=null&&T.contains(i)||(d.value=!1))}function Pe(c){c.key==="Escape"&&(d.value=!1)}function Hn(){ce();const c=()=>{jn(),v=requestAnimationFrame(c)};c(),document.addEventListener("pointerdown",Oe,!0),window.addEventListener("keydown",Pe)}function ce(){v!=null&&(cancelAnimationFrame(v),v=null),document.removeEventListener("pointerdown",Oe,!0),window.removeEventListener("keydown",Pe)}function Yn(){d.value=!d.value}function Qn(c){if(u.value=c,G&&clearTimeout(G),!c.trim()){q.value=!1,p.value=[];return}q.value=!0,G=setTimeout(async()=>{p.value=await _(c.trim()),q.value=!1},260)}async function de(c){u.value="",p.value=[],await b(c)}function Xe(){e.nextTick(()=>{const c=Le.value;if(!c)return;const i=c.querySelector(".wx-hour-item--active");i&&c.scrollTo({left:Math.max(i.offsetLeft-16,0),behavior:"smooth"})})}return e.watch($,()=>{d.value&&Xe()}),e.watch(d,c=>{if(c){Xe(),e.nextTick(()=>{Hn()});return}ce()}),e.onBeforeUnmount(()=>{G&&clearTimeout(G),ce()}),(c,i)=>(e.openBlock(),e.createElementBlock(e.Fragment,null,[e.createVNode(e.unref(He.Tooltip),{title:e.unref(t.$t)("plugin.weather-widget.ui.open_weather"),placement:"bottom"},{default:e.withCtx(()=>[e.createElementVNode("button",{ref_key:"triggerRef",ref:le,type:"button",class:"wx-trigger","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.open_weather"),"aria-expanded":d.value,onClick:Yn},[e.createElementVNode("span",$t,[e.unref(s)&&!e.unref(V)?(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:0,icon:`lucide:${ee(e.unref(s).weather_code,e.unref(s).is_day)}`,class:"wx-trigger__icon"},null,8,["icon"])):e.unref(V)?(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:1,icon:"lucide:loader-2",class:"wx-trigger__icon animate-spin"})):(e.openBlock(),e.createBlock(e.unref(t.IconifyIcon),{key:2,icon:"lucide:cloud-off",class:"wx-trigger__icon"}))]),e.createElementVNode("span",zt,[e.createElementVNode("small",null,e.toDisplayString(e.unref(r)),1),e.createElementVNode("strong",null,[e.unref(s)&&!e.unref(V)?(e.openBlock(),e.createElementBlock(e.Fragment,{key:0},[e.createTextVNode(e.toDisplayString(e.unref(k)(e.unref(s).temperature,e.unref(o)))+"° ",1)],64)):(e.openBlock(),e.createElementBlock(e.Fragment,{key:1},[e.createTextVNode(" -- ")],64))])])],8,Ct)]),_:1},8,["title"]),(e.openBlock(),e.createBlock(e.Teleport,{to:"body"},[d.value?(e.openBlock(),e.createElementBlock("div",{key:0,class:"weather-popover-immersive-overlay",style:e.normalizeStyle(Se.value)},[e.createElementVNode("section",{ref_key:"panelRef",ref:se,class:e.normalizeClass(["wx-panel wx-noise",[Me.value.bgClass,`wx-scene--${Me.value.scene}`]])},[i[10]||(i[10]=e.createElementVNode("div",{class:"wx-panel__veil"},null,-1)),e.createVNode(e.Transition,{name:"wx-fade-slide",mode:"out-in"},{default:e.withCtx(()=>{var y,T;return[e.unref(I)?(e.openBlock(),e.createElementBlock("div",Bt,[e.createElementVNode("header",Dt,[e.createElementVNode("button",{type:"button",class:"wx-icon-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.back"),onClick:i[0]||(i[0]=a=>I.value=!1)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:chevron-left",class:"size-4"})],8,It),e.createElementVNode("h3",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.change_city")),1),e.createElementVNode("button",{type:"button",class:"wx-icon-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.close"),onClick:i[1]||(i[1]=a=>d.value=!1)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:x",class:"size-4"})],8,Tt)]),e.createElementVNode("div",Lt,[e.createElementVNode("span",St,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.current_city")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref(r)),1)]),e.createElementVNode("label",At,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:search",class:"size-4 opacity-70"}),e.createElementVNode("input",{value:u.value,placeholder:e.unref(t.$t)("plugin.weather-widget.ui.search_city"),onInput:i[2]||(i[2]=a=>Qn(a.target.value))},null,40,Wt)]),e.createElementVNode("div",Rt,[u.value.trim()?(e.openBlock(),e.createElementBlock("div",Ft,[q.value?(e.openBlock(),e.createElementBlock("div",qt,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:loader-2",class:"size-4 animate-spin"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.loading")),1)])):e.createCommentVNode("",!0),(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(p.value,a=>(e.openBlock(),e.createElementBlock("button",{key:`search-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>de(a)},[e.createElementVNode("span",Ut,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:map-pin",class:"size-3.5 opacity-65"}),e.createElementVNode("span",Ot,e.toDisplayString(a.name),1)]),e.unref(ye)(a)?(e.openBlock(),e.createElementBlock("span",Pt,e.toDisplayString(e.unref(ye)(a)),1)):e.createCommentVNode("",!0)],8,Mt))),128)),!q.value&&p.value.length===0?(e.openBlock(),e.createElementBlock("div",Xt,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.error.city_not_found")),1)):e.createCommentVNode("",!0)])):e.createCommentVNode("",!0),e.createElementVNode("button",{type:"button",class:"wx-locate-btn",disabled:e.unref(h),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.auto_locate"),onClick:i[3]||(i[3]=(...a)=>e.unref(x)&&e.unref(x)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(h)?"lucide:loader-2":"lucide:locate",class:e.normalizeClass(e.unref(h)?"size-4 animate-spin":"size-4")},null,8,["icon","class"]),e.createTextVNode(" "+e.toDisplayString(e.unref(h)?e.unref(t.$t)("plugin.weather-widget.ui.locating"):e.unref(t.$t)("plugin.weather-widget.ui.auto_locate")),1)],8,jt),e.unref(z)?(e.openBlock(),e.createElementBlock("div",Ht,e.toDisplayString(e.unref(t.$t)(`plugin.weather-widget.error.${e.unref(z)}`)),1)):e.createCommentVNode("",!0),e.unref(l).length>0?(e.openBlock(),e.createElementBlock("div",Yt,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.recent_cities")),1),e.createElementVNode("div",Qt,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(e.unref(l),a=>(e.openBlock(),e.createElementBlock("button",{key:`recent-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>de(a)},[e.createElementVNode("span",Kt,e.toDisplayString(a.name),1)],8,Gt))),128))])])):e.createCommentVNode("",!0),e.createElementVNode("div",Jt,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.popular_cities")),1),e.createElementVNode("div",Zt,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(e.unref(Ye),a=>(e.openBlock(),e.createElementBlock("button",{key:`popular-${a.latitude}-${a.longitude}`,type:"button",class:"wx-city-chip",onClick:L=>de(a)},[e.createElementVNode("span",en,e.toDisplayString(a.name),1)],8,vt))),128))])])])])):(e.openBlock(),e.createElementBlock("div",tn,[e.unref(V)&&!e.unref(s)?(e.openBlock(),e.createElementBlock("div",nn,[...i[8]||(i[8]=[e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--lg"},null,-1),e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--md"},null,-1),e.createElementVNode("div",{class:"wx-skeleton wx-skeleton--grid"},null,-1)])])):e.unref(O)&&!e.unref(s)?(e.openBlock(),e.createElementBlock("div",an,[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:cloud-off",class:"size-10 opacity-65"}),e.createElementVNode("p",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.error")),1),e.createElementVNode("button",{type:"button",class:"wx-action-btn",onClick:i[4]||(i[4]=(...a)=>e.unref(f)&&e.unref(f)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:refresh-cw",class:"size-4"}),e.createTextVNode(" "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.retry")),1)])])):e.unref(s)?(e.openBlock(),e.createElementBlock(e.Fragment,{key:2},[e.createElementVNode("header",on,[e.createElementVNode("button",{type:"button",class:"wx-city-btn","aria-label":e.unref(t.$t)("plugin.weather-widget.ui.change_city"),onClick:i[5]||(i[5]=a=>I.value=!0)},[e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:map-pin",class:"size-3.5 opacity-70"}),e.createElementVNode("span",ln,e.toDisplayString(e.unref(r)),1),e.createVNode(e.unref(t.IconifyIcon),{icon:"lucide:chevron-down",class:"size-3.5 opacity-60"})],8,rn),e.createElementVNode("div",sn,[e.createElementVNode("span",cn,e.toDisplayString(qe.value),1),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref(h),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.auto_locate"),onClick:i[6]||(i[6]=(...a)=>e.unref(x)&&e.unref(x)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(h)?"lucide:loader-2":"lucide:locate",class:e.normalizeClass(e.unref(h)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,dn),e.createElementVNode("button",{type:"button",class:"wx-icon-btn",disabled:e.unref(D),"aria-label":e.unref(t.$t)("plugin.weather-widget.ui.refresh"),onClick:i[7]||(i[7]=(...a)=>e.unref(f)&&e.unref(f)(...a))},[e.createVNode(e.unref(t.IconifyIcon),{icon:e.unref(D)?"lucide:loader-2":"lucide:refresh-cw",class:e.normalizeClass(e.unref(D)?"size-4 animate-spin":"size-4")},null,8,["icon","class"])],8,pn)])]),i[9]||(i[9]=e.createElementVNode("div",{class:"wx-scene","aria-hidden":"true"},[e.createElementVNode("span",{class:"wx-scene__orb"}),e.createElementVNode("span",{class:"wx-scene__cloud wx-scene__cloud--1"}),e.createElementVNode("span",{class:"wx-scene__cloud wx-scene__cloud--2"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--1"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--2"}),e.createElementVNode("span",{class:"wx-scene__spark wx-scene__spark--3"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--1"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--2"}),e.createElementVNode("span",{class:"wx-scene__drop wx-scene__drop--3"}),e.createElementVNode("span",{class:"wx-scene__flake wx-scene__flake--1"}),e.createElementVNode("span",{class:"wx-scene__flake wx-scene__flake--2"}),e.createElementVNode("span",{class:"wx-scene__mist wx-scene__mist--1"}),e.createElementVNode("span",{class:"wx-scene__mist wx-scene__mist--2"}),e.createElementVNode("span",{class:"wx-scene__flash"})],-1)),e.createElementVNode("div",xn,[e.createElementVNode("div",wn,[e.createElementVNode("span",null,e.toDisplayString(qe.value),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.last_updated"))+" "+e.toDisplayString(Mn.value),1)]),e.createElementVNode("div",gn,[e.createElementVNode("div",fn,[e.createElementVNode("div",hn,e.toDisplayString(e.unref(k)(e.unref(s).temperature,e.unref(o)))+"° ",1),e.createElementVNode("div",un,e.toDisplayString(Ue(e.unref(s))),1),e.createElementVNode("div",mn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.feels_like"))+" "+e.toDisplayString(e.unref(k)(e.unref(s).apparent_temperature,e.unref(o)))+"°"+e.toDisplayString(We.value),1),K.value?(e.openBlock(),e.createElementBlock("span",_n,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.high_short"))+" "+e.toDisplayString(e.unref(k)(K.value.temp_max,e.unref(o)))+"° / "+e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.low_short"))+" "+e.toDisplayString(e.unref(k)(K.value.temp_min,e.unref(o)))+"° ",1)):e.createCommentVNode("",!0)])]),e.createElementVNode("div",bn,[e.createElementVNode("div",yn,[e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ee(e.unref(s).weather_code,e.unref(s).is_day)}`,class:"wx-hero__icon"},null,8,["icon"])]),e.createElementVNode("span",kn,e.toDisplayString(We.value),1)])]),e.unref(F)?(e.openBlock(),e.createElementBlock("div",En,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.data_stale")),1)):e.createCommentVNode("",!0)]),e.createElementVNode("section",Nn,[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Un.value,a=>(e.openBlock(),e.createElementBlock("article",{key:a.key,class:"wx-chip"},[e.createElementVNode("span",null,e.toDisplayString(a.label),1),e.createElementVNode("strong",{style:e.normalizeStyle(a.tone?{color:a.tone}:void 0)},e.toDisplayString(a.value),5),a.note?(e.openBlock(),e.createElementBlock("small",{key:0,style:e.normalizeStyle(a.tone?{color:a.tone}:void 0)},e.toDisplayString(a.note),5)):e.createCommentVNode("",!0)]))),128))]),Fe.value.length>0?(e.openBlock(),e.createElementBlock("section",Vn,[e.createElementVNode("div",Cn,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.hourly_forecast")),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.hourly_digest")),1)]),e.createElementVNode("div",{ref_key:"hourlyScrollRef",ref:Le,class:"wx-hourly-scroll"},[(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Fe.value,(a,L)=>(e.openBlock(),e.createElementBlock("article",{key:`hour-${L}`,class:e.normalizeClass(["wx-hour-item",a.is_current?"wx-hour-item--active":""])},[e.createElementVNode("span",$n,e.toDisplayString(On(a.time,a.is_current)),1),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ee(a.weather_code,e.unref(s).is_day)}`,class:"size-4"},null,8,["icon"]),e.createElementVNode("span",zn,e.toDisplayString(e.unref(k)(a.temperature,e.unref(o)))+"° ",1)],2))),128))],512)])):e.createCommentVNode("",!0),e.createElementVNode("div",Bn,[e.createElementVNode("article",Dn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.sunrise")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref(Ee)((y=K.value)==null?void 0:y.sunrise)),1)]),e.createElementVNode("article",In,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.sunset")),1),e.createElementVNode("strong",null,e.toDisplayString(e.unref(Ee)((T=K.value)==null?void 0:T.sunset)),1)])]),Re.value.length>0?(e.openBlock(),e.createElementBlock("section",Tn,[e.createElementVNode("div",Ln,[e.createElementVNode("h4",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.forecast")),1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.forecast_digest")),1)]),(e.openBlock(!0),e.createElementBlock(e.Fragment,null,e.renderList(Re.value,(a,L)=>(e.openBlock(),e.createElementBlock("article",{key:a.date,class:"wx-forecast-row"},[e.createElementVNode("div",Sn,[e.createElementVNode("span",null,e.toDisplayString(e.unref(Ce)(a.date,L,e.unref(t.$t))),1),e.createElementVNode("small",null,e.toDisplayString(Ue(a)),1)]),e.createVNode(e.unref(t.IconifyIcon),{icon:`lucide:${ee(a.weather_code,e.unref(s).is_day)}`,class:"size-4"},null,8,["icon"]),e.createElementVNode("div",An,[e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.high_short"))+" "+e.toDisplayString(e.unref(k)(a.temp_max,e.unref(o)))+"° ",1),e.createElementVNode("span",null,e.toDisplayString(e.unref(t.$t)("plugin.weather-widget.ui.low_short"))+" "+e.toDisplayString(e.unref(k)(a.temp_min,e.unref(o)))+"° ",1)])]))),128))])):e.createCommentVNode("",!0)],64)):e.createCommentVNode("",!0)]))]}),_:1})],2)],4)):e.createCommentVNode("",!0)]))],64))}}),Ie={_meta:{lang:"zh"},ui:{temperature:"温度",feels_like:"体感温度",humidity:"湿度",wind_speed:"风速",uv_index:"紫外线",aqi:"空气质量",sunrise:"日出",sunset:"日落",hourly_forecast:"小时预报",hourly_digest:"未来几小时走势",forecast:"未来预报",forecast_digest:"接下来几天概览",current_conditions:"当前天气",current_city:"当前城市",last_updated:"更新于",live_data:"实时",cached_data:"缓存",change_city:"切换城市",search_city:"搜索城市...",recent_cities:"最近城市",popular_cities:"热门城市",auto_locate:"自动定位",locating:"定位中...",loading:"加载天气中...",error:"天气数据获取失败",retry:"重试",refresh:"刷新天气",open_weather:"打开天气面板",back:"返回",close:"关闭",today:"今天",tomorrow:"明天",day_after:"后天",now:"现在",weekday_0:"周日",weekday_1:"周一",weekday_2:"周二",weekday_3:"周三",weekday_4:"周四",weekday_5:"周五",weekday_6:"周六",data_stale:"数据可能已过期",high_short:"高",low_short:"低",unit_kmh:"公里/小时",unit_mph:"英里/小时"},error:{city_not_found:"未找到该城市",api_timeout:"天气服务请求超时",network:"网络错误，请稍后重试",locate_failed:"定位失败，请检查权限",locate_fallback:"无法识别城市，使用坐标定位"},aqi_level:{good:"优",moderate:"良",unhealthy_sensitive:"轻度",unhealthy:"中度",very_unhealthy:"重度",hazardous:"严重",na:"--"}},Te={_meta:{lang:"en"},ui:{temperature:"Temperature",feels_like:"Feels Like",humidity:"Humidity",wind_speed:"Wind",uv_index:"UV Index",aqi:"Air Quality",sunrise:"Sunrise",sunset:"Sunset",hourly_forecast:"Hourly",hourly_digest:"Next few hours",forecast:"Forecast",forecast_digest:"Upcoming days",current_conditions:"Current Conditions",current_city:"Current City",last_updated:"Updated",live_data:"Live",cached_data:"Cached",change_city:"Change City",search_city:"Search city...",recent_cities:"Recent Cities",popular_cities:"Popular Cities",auto_locate:"Auto Locate",locating:"Locating...",loading:"Loading weather...",error:"Failed to load weather data",retry:"Retry",refresh:"Refresh weather",open_weather:"Open weather panel",back:"Back",close:"Close",today:"Today",tomorrow:"Tomorrow",day_after:"Day After",now:"Now",weekday_0:"Sun",weekday_1:"Mon",weekday_2:"Tue",weekday_3:"Wed",weekday_4:"Thu",weekday_5:"Fri",weekday_6:"Sat",data_stale:"Data may be outdated",high_short:"H",low_short:"L",unit_kmh:"km/h",unit_mph:"mph"},error:{city_not_found:"City not found",api_timeout:"Weather service timed out",network:"Network error, please try again",locate_failed:"Location failed, check permissions",locate_fallback:"Could not identify city, using coordinates"},aqi_level:{good:"Good",moderate:"Moderate",unhealthy_sensitive:"Sensitive",unhealthy:"Unhealthy",very_unhealthy:"Very Unhealthy",hazardous:"Hazardous",na:"--"}},Rn=[`
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
`);function Fn(){const n=window.NovusPluginShared;if(n!=null&&n.registerLocale&&(n.registerLocale("zh-CN","plugin.weather-widget",Ie),n.registerLocale("zh","plugin.weather-widget",Ie),n.registerLocale("en-US","plugin.weather-widget",Te),n.registerLocale("en","plugin.weather-widget",Te)),!document.getElementById("wx-plugin-styles")){const r=document.createElement("style");r.id="wx-plugin-styles",r.textContent=Rn,document.head.appendChild(r)}}E.WeatherDashboardWidget=Vt,E.WeatherHeaderWidget=Wn,E.setup=Fn,Object.defineProperty(E,Symbol.toStringTag,{value:"Module"})}));
