import type { ReactNode } from "react";

type NavLinkProps = {
  children: ReactNode;
  currentPath: string;
  href: string;
};

export default function NavLink({ children, currentPath, href }: NavLinkProps) {
  const isActive = currentPath === href;

  return (
    <a className="nav-link" href={href} aria-current={isActive ? "page" : undefined}>
      {children}
    </a>
  );
}
