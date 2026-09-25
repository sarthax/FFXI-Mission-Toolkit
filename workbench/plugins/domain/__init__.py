"""Reusable content-framework and system-specific domain plugins."""
from .base import ContentArchetype, DomainPlugin, DomainPluginSpec, PluginContext, PluginFinding
from .registry import DomainPluginRegistry
from .planning import plugin_findings_to_actions, apply_plugin_reshape_findings, apply_plugin_proposal_findings
from .battlefield_dsp import DspBattlefieldMember, DspBattlefieldMembershipProposal, DspBattlefieldPolicyProposal, DspBattlefieldCallbackSurface, DspBattlefieldCallbackAdaptationPlan, DspBattlefieldRepresentationPlan, propose_dsp_battlefield_membership, propose_dsp_battlefield_policy, analyze_dsp_battlefield_callbacks, plan_dsp_battlefield_callback_adaptation, plan_dsp_battlefield_representation, generated_outputs_for_dsp_battlefield, battlefield_representation_finding
from .battlefield_lsb import LsbBattlefieldPolicySurface, LsbBattlefieldMobGroups, extract_lsb_battlefield_policy, extract_lsb_mission_level_cap, extract_lsb_battlefield_mob_groups
from .battlefield_validation import GeneratedSqlValidation, validate_dsp_battlefield_proposals
from .mission_representation import MissionRequirement, MissionRepresentation, MissionRepresentationPlan, plan_mission_representation
from .mission_dsp import MissionPatchProposal, generated_mission_patch_proposals, mission_proposal_finding
from .builtin import (
    ARCHETYPES,
    AssaultPlugin,
    BattlefieldFamilyPlugin,
    MinigamePlugin,
    MultiZoneProgressionPlugin,
    QuestMissionPlugin,
    default_registry,
)

__all__=[
    "ContentArchetype","DomainPlugin","DomainPluginSpec","PluginContext","PluginFinding",
    "DomainPluginRegistry","plugin_findings_to_actions","apply_plugin_reshape_findings","apply_plugin_proposal_findings","DspBattlefieldMember","DspBattlefieldMembershipProposal","DspBattlefieldPolicyProposal","DspBattlefieldCallbackSurface","DspBattlefieldCallbackAdaptationPlan","DspBattlefieldRepresentationPlan","propose_dsp_battlefield_membership","propose_dsp_battlefield_policy","analyze_dsp_battlefield_callbacks","plan_dsp_battlefield_callback_adaptation","plan_dsp_battlefield_representation","generated_outputs_for_dsp_battlefield","battlefield_representation_finding","LsbBattlefieldPolicySurface","LsbBattlefieldMobGroups","extract_lsb_battlefield_policy","extract_lsb_mission_level_cap","extract_lsb_battlefield_mob_groups","GeneratedSqlValidation","validate_dsp_battlefield_proposals","MissionRequirement","MissionRepresentation","MissionRepresentationPlan","plan_mission_representation","MissionPatchProposal","generated_mission_patch_proposals","mission_proposal_finding","ARCHETYPES","BattlefieldFamilyPlugin","QuestMissionPlugin",
    "MultiZoneProgressionPlugin","MinigamePlugin","AssaultPlugin","default_registry",
]
