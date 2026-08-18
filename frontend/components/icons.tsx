import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function base(props: IconProps) {
  return {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export const IconRadar = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M19.07 4.93A10 10 0 1 0 22 12" />
    <path d="M16.24 7.76A6 6 0 1 0 18 12" />
    <path d="M12 12 22 2" />
    <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
  </svg>
);

export const IconBolt = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
  </svg>
);

export const IconHash = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18" />
  </svg>
);

export const IconFeed = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16" />
    <circle cx="5" cy="19" r="1.4" fill="currentColor" stroke="none" />
  </svg>
);

export const IconBeaker = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" />
    <path d="M7 15h10" />
  </svg>
);

export const IconUser = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </svg>
);

export const IconDraft = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 4h11l5 5v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4Z" />
    <path d="M14 4v6h6M8 14h8M8 17h5" />
  </svg>
);

export const IconGraph = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 20V4M4 20h16" />
    <path d="m7 15 3-4 3 2 5-7" />
  </svg>
);

export const IconGauge = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 14 16 9" />
    <path d="M4 18a8 8 0 1 1 16 0" />
    <circle cx="12" cy="14" r="1.4" fill="currentColor" stroke="none" />
  </svg>
);

export const IconBell = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7Z" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </svg>
);

export const IconPower = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3v9" />
    <path d="M6.4 6.4a8 8 0 1 0 11.2 0" />
  </svg>
);

export const IconMenu = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

export const IconClose = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);
