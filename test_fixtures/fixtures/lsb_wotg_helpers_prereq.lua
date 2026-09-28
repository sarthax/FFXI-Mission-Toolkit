-----------------------------------
-- WotG helper prerequisite fixture
-----------------------------------
xi = xi or {}
xi.wotg = xi.wotg or {}
xi.wotg.helpers = xi.wotg.helpers or {}

xi.wotg.helpers.hasCompletedFirstQuest = function(player)
    return player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.STEAMED_RAMS) or
        player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.SNAKE_ON_THE_PLAINS) or
        player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.THE_FIGHTING_FOURTH)
end

xi.wotg.helpers.meetsMission3Reqs = function(player)
    return player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.CLAWS_OF_THE_GRIFFON) or
        player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.THE_TIGRESS_STRIKES) or
        player:hasCompletedQuest(xi.questLog.CRYSTAL_WAR, xi.quest.id.crystalWar.FIRES_OF_DISCONTENT)
end
