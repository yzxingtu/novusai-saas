export interface HelpCenterFaq {
  answer: string;
  icon: string;
  question: string;
}

export interface HelpCenterJourney {
  description: string;
  icon: string;
  path: string;
  title: string;
}

export interface HelpCenterResource {
  description: string;
  icon: string;
  path: string;
  title: string;
}

interface TranslateParams {
  [key: string]: number | string;
}

type TranslateFn = (key: string, params?: TranslateParams) => string;

export function buildHelpJourneys(t: TranslateFn): HelpCenterJourney[] {
  return [
    {
      description: t('user.helpCenter.journeys.discover.desc'),
      icon: 'lucide:compass',
      path: '/agents',
      title: t('user.helpCenter.journeys.discover.title'),
    },
    {
      description: t('user.helpCenter.journeys.chat.desc'),
      icon: 'lucide:messages-square',
      path: '/ai-chat',
      title: t('user.helpCenter.journeys.chat.title'),
    },
    {
      description: t('user.helpCenter.journeys.settings.desc'),
      icon: 'lucide:shield-check',
      path: '/settings/profile',
      title: t('user.helpCenter.journeys.settings.title'),
    },
  ];
}

export function buildHelpFaqs(t: TranslateFn): HelpCenterFaq[] {
  return [
    {
      answer: t('user.helpCenter.faqs.agent.answer'),
      icon: 'lucide:bot',
      question: t('user.helpCenter.faqs.agent.question'),
    },
    {
      answer: t('user.helpCenter.faqs.upload.answer'),
      icon: 'lucide:paperclip',
      question: t('user.helpCenter.faqs.upload.question'),
    },
    {
      answer: t('user.helpCenter.faqs.history.answer'),
      icon: 'lucide:history',
      question: t('user.helpCenter.faqs.history.question'),
    },
    {
      answer: t('user.helpCenter.faqs.memory.answer'),
      icon: 'lucide:brain',
      question: t('user.helpCenter.faqs.memory.question'),
    },
    {
      answer: t('user.helpCenter.faqs.export.answer'),
      icon: 'lucide:download',
      question: t('user.helpCenter.faqs.export.question'),
    },
    {
      answer: t('user.helpCenter.faqs.help.answer'),
      icon: 'lucide:life-buoy',
      question: t('user.helpCenter.faqs.help.question'),
    },
  ];
}

export function buildHelpResources(t: TranslateFn): HelpCenterResource[] {
  return [
    {
      description: t('user.helpCenter.resources.agents.desc'),
      icon: 'lucide:bot',
      path: '/agents',
      title: t('user.helpCenter.resources.agents.title'),
    },
    {
      description: t('user.helpCenter.resources.workspace.desc'),
      icon: 'lucide:layout-panel-top',
      path: '/ai-chat',
      title: t('user.helpCenter.resources.workspace.title'),
    },
    {
      description: t('user.helpCenter.resources.profile.desc'),
      icon: 'lucide:user-round-cog',
      path: '/settings/profile',
      title: t('user.helpCenter.resources.profile.title'),
    },
  ];
}
