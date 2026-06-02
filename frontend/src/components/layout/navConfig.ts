import {
  Activity, Search, BrainCircuit, BookOpen,
  CalendarDays, Timer,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Single source of truth for primary navigation — shared by the desktop
 *  Sidebar and the mobile nav drawer so they never drift (UI_REVIEW U-1). */
export const navGroups: NavGroup[] = [
  {
    label: 'Recall loop',
    items: [
      { to: '/',         label: 'Health',   icon: Activity, exact: true },
      { to: '/search',   label: 'Discover', icon: Search },
      { to: '/library',  label: 'Library',  icon: BookOpen },
      { to: '/review',   label: 'Practice', icon: BrainCircuit },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/calendar', label: 'Calendar', icon: CalendarDays },
      { to: '/pomodoro', label: 'Focus',    icon: Timer },
    ],
  },
];
