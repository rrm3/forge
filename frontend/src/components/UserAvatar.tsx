import { useState } from 'react';
import Tooltip from '@mui/material/Tooltip';

interface UserAvatarProps {
  name: string;
  avatarUrl?: string;
  title?: string;
  department?: string;
  size?: number;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

export function UserAvatar({ name, avatarUrl, title, department, size = 28 }: UserAvatarProps) {
  const [imgError, setImgError] = useState(false);
  const showImage = avatarUrl && !imgError;
  const fontSize = Math.max(9, Math.round(size * 0.39));

  const tooltipLines = [name];
  if (title) tooltipLines.push(title);
  if (department) tooltipLines.push(department);
  const hasTooltip = tooltipLines.length > 1 || name;

  const circle = (
    <div
      className="flex items-center justify-center rounded-full shrink-0 overflow-hidden"
      style={{
        width: size,
        height: size,
        backgroundColor: showImage ? 'transparent' : '#159AC9',
      }}
    >
      {showImage ? (
        <img
          src={avatarUrl}
          alt={name}
          onError={() => setImgError(true)}
          className="w-full h-full object-cover"
          referrerPolicy="no-referrer"
        />
      ) : (
        <span
          style={{
            color: '#FFFFFF',
            fontSize,
            fontWeight: 600,
            fontFamily: "'Satoshi', system-ui, sans-serif",
            lineHeight: 1,
          }}
        >
          {getInitials(name)}
        </span>
      )}
    </div>
  );

  if (!hasTooltip) return circle;

  return (
    <Tooltip
      title={
        <div style={{ lineHeight: 1.4 }}>
          <div style={{ fontWeight: 600 }}>{name}</div>
          {title && <div style={{ opacity: 0.85 }}>{title}</div>}
          {department && <div style={{ opacity: 0.7 }}>{department}</div>}
        </div>
      }
      arrow
      placement="bottom"
    >
      {circle}
    </Tooltip>
  );
}
