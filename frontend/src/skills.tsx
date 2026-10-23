// Skills: the procedural knowledge HANNI loads per task.
import { usePrivateResource } from "./feature_types";

type Skill = { name: string; description: string; triggers: string[] };
type SkillData = { skills: Skill[] };

export function SkillsPage({ token }: { token: string }) {
  const data = usePrivateResource<SkillData>("/api/skills", token, 60000);
  const skills = data.data?.skills ?? [];
  return (
    <section className="screen-section">
      <div className="section-title">
        <h2>Skills</h2><span>{skills.length} learned procedures, matched per task</span>
      </div>
      {data.error && <p className="error">Skills inventory unavailable: {data.error}</p>}
      {skills.map((skill) => (
        <details key={skill.name}>
          <summary><strong>{skill.name}</strong>{" "}<span className="subtle">{skill.description.slice(0, 120)}</span></summary>
          <p className="subtle">Triggers: {skill.triggers.slice(0, 12).join(", ") || "description keywords"}</p>
        </details>
      ))}
      {!skills.length && !data.error && <p className="subtle">No skills installed. Add markdown skills to the skills directory.</p>}
    </section>
  );
}
