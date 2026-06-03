/**
 * Scene variants and animations.
 */
export const WX_SCENE = `
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
`;
