const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function Icon({ name, size = 16, ...rest }) {
  const props = { width: size, height: size, viewBox: "0 0 24 24", ...rest };
  switch (name) {
    case "pipeline":
      return (
        <svg {...props}>
          <path {...stroke} d="M4 19V9m6 10V5m6 14v-8" />
          <circle {...stroke} cx="4" cy="6" r="1.5" />
          <circle {...stroke} cx="10" cy="3" r="1.5" />
          <circle {...stroke} cx="16" cy="8" r="1.5" />
        </svg>
      );
    case "brain":
      return (
        <svg {...props}>
          <path
            {...stroke}
            d="M9 4.5a2.5 2.5 0 0 0-2.5 2.5v.2A2.8 2.8 0 0 0 4 9.8a2.8 2.8 0 0 0 1.5 2.5A2.8 2.8 0 0 0 4 14.7a2.8 2.8 0 0 0 2.5 2.8v.5A2.5 2.5 0 0 0 9 20.5h1V4.5H9zM14 4.5h1A2.5 2.5 0 0 1 17.5 7v.2A2.8 2.8 0 0 1 20 9.8a2.8 2.8 0 0 1-1.5 2.5A2.8 2.8 0 0 1 20 14.7a2.8 2.8 0 0 1-2.5 2.8v.5A2.5 2.5 0 0 1 15 20.5h-1"
          />
        </svg>
      );
    case "doc":
      return (
        <svg {...props}>
          <path {...stroke} d="M7 3h7l4 4v14H7z" />
          <path {...stroke} d="M14 3v4h4M9 12h7M9 16h7M9 8h2" />
        </svg>
      );
    case "gear":
      return (
        <svg {...props}>
          <circle {...stroke} cx="12" cy="12" r="3" />
          <path
            {...stroke}
            d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4.8a7 7 0 0 0-2-1.2L14 3h-4l-.4 2.4a7 7 0 0 0-2 1.2L5 5.8l-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-.8a7 7 0 0 0 2 1.2L10 21h4l.4-2.4a7 7 0 0 0 2-1.2l2.4.8 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"
          />
        </svg>
      );
    case "help":
      return (
        <svg {...props}>
          <circle {...stroke} cx="12" cy="12" r="9" />
          <path {...stroke} d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7" />
          <circle cx="12" cy="17" r="1" fill="currentColor" />
        </svg>
      );
    case "plus":
      return (
        <svg {...props}>
          <path {...stroke} d="M12 5v14M5 12h14" />
        </svg>
      );
    case "logout":
      return (
        <svg {...props}>
          <path {...stroke} d="M15 4h4v16h-4" />
          <path {...stroke} d="M10 8l-4 4 4 4M6 12h11" />
        </svg>
      );
    case "play":
      return (
        <svg {...props}>
          <path {...stroke} d="M7 5l12 7-12 7z" />
        </svg>
      );
    case "refresh":
      return (
        <svg {...props}>
          <path {...stroke} d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
          <path {...stroke} d="M21 3v5h-5" />
          <path {...stroke} d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
          <path {...stroke} d="M3 21v-5h5" />
        </svg>
      );
    case "bell":
      return (
        <svg {...props}>
          <path {...stroke} d="M18 16H6l1.5-2v-4a4.5 4.5 0 1 1 9 0v4z" />
          <path {...stroke} d="M10 20a2 2 0 0 0 4 0" />
        </svg>
      );
    case "settings-dot":
      return (
        <svg {...props}>
          <circle {...stroke} cx="12" cy="12" r="9" />
          <circle cx="12" cy="12" r="2" fill="currentColor" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle {...stroke} cx="11" cy="11" r="7" />
          <path {...stroke} d="M20 20l-3.5-3.5" />
        </svg>
      );
    case "pin":
      return (
        <svg {...props}>
          <path
            {...stroke}
            d="M12 22s7-7.5 7-13a7 7 0 1 0-14 0c0 5.5 7 13 7 13z"
          />
          <circle {...stroke} cx="12" cy="9" r="2.5" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <path {...stroke} d="M5 12l5 5L20 7" />
        </svg>
      );
    case "x":
      return (
        <svg {...props}>
          <path {...stroke} d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    case "sparkle":
      return (
        <svg {...props}>
          <path
            {...stroke}
            d="M12 3l1.8 4.5L18 9l-4.2 1.5L12 15l-1.8-4.5L6 9l4.2-1.5z"
          />
          <path {...stroke} d="M18 15l.8 2 2 .8-2 .7L18 20l-.7-1.5-2-.7 2-.8z" />
        </svg>
      );
    case "warning":
      return (
        <svg {...props}>
          <path {...stroke} d="M12 4l9 16H3z" />
          <path {...stroke} d="M12 10v4" />
          <circle cx="12" cy="17" r="1" fill="currentColor" />
        </svg>
      );
    case "bookmark":
      return (
        <svg {...props}>
          <path {...stroke} d="M6 4h12v17l-6-4-6 4z" />
        </svg>
      );
    case "clock":
      return (
        <svg {...props}>
          <circle {...stroke} cx="12" cy="12" r="9" />
          <path {...stroke} d="M12 7v5l3 2" />
        </svg>
      );
    case "users":
      return (
        <svg {...props}>
          <circle {...stroke} cx="9" cy="9" r="3" />
          <path {...stroke} d="M3 19c0-3 3-5 6-5s6 2 6 5" />
          <path {...stroke} d="M16 11a3 3 0 0 0 0-6" />
          <path {...stroke} d="M17 19c0-2-1-3.5-2.5-4.4" />
        </svg>
      );
    case "money":
      return (
        <svg {...props}>
          <rect {...stroke} x="3" y="6" width="18" height="12" rx="2" />
          <circle {...stroke} cx="12" cy="12" r="2.5" />
          <path {...stroke} d="M6 10v4M18 10v4" />
        </svg>
      );
    case "arrow-up-right":
      return (
        <svg {...props}>
          <path {...stroke} d="M7 17L17 7M9 7h8v8" />
        </svg>
      );
    case "wand":
      return (
        <svg {...props}>
          <path {...stroke} d="M4 20l10-10" />
          <path {...stroke} d="M14 6l2-2 2 2-2 2zM18 10l1.5-1.5L21 10l-1.5 1.5z" />
        </svg>
      );
    default:
      return <svg {...props} />;
  }
}
