import { NavLink } from "react-router-dom";

export function AppNav() {
  return (
    <nav className="app-nav">
      <NavLink
        to="/home"
        className={({ isActive }) => `nav-tab${isActive ? " nav-tab-active" : ""}`}
      >
        檔案上傳
      </NavLink>
      <NavLink
        to="/files"
        className={({ isActive }) => `nav-tab${isActive ? " nav-tab-active" : ""}`}
      >
        檔案管理
      </NavLink>
      <NavLink
        to="/query"
        className={({ isActive }) => `nav-tab${isActive ? " nav-tab-active" : ""}`}
      >
        查詢 / 閱覽
      </NavLink>
    </nav>
  );
}
