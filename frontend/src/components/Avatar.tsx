import type { IdentityOut } from "../types/api";

type Props = {
  identity?: Pick<IdentityOut, "name" | "avatar_url"> | null;
  size?: "sm" | "md" | "lg";
};

export function Avatar({ identity, size = "md" }: Props) {
  const src = identity?.avatar_url || "/default-assistant.png";
  return (
    <img
      className={`avatar avatar-${size}`}
      src={src}
      alt={identity ? `${identity.name}头像` : "默认助手头像"}
    />
  );
}
