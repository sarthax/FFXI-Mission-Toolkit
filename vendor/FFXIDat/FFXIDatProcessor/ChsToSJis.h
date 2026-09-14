#pragma once

#include <string>
#include <map>

class ChsToSJis
{
	std::map<int, std::u8string> repMap;
public:
	std::u8string ReplaceHanzi(std::u8string in);

	ChsToSJis();

	static ChsToSJis &Instance();
};

