import sys
import argparse
import csv
import tkinter as tk
from PIL import ImageTk,Image


N_ROWS=32
N_COLS=23
FIRST_ROW=1
FIRST_COL=ord('A')
ROWS=[118, 747]
DROW=(ROWS[1]-ROWS[0])/N_ROWS
COLS=[26, 480]
DCOL=(COLS[1]-COLS[0])/N_COLS
N_TURNS=40
TURNS_COL=538
TURNS_ROW=[40, 721]
DTURN=(TURNS_ROW[1]-TURNS_ROW[0])/N_TURNS
PROB_RECT_OFFSET=2

NUM_MOVES_PER_TURN=4
NUM_MOVES_PER_TURN_SURGE=6
MOTION_DETECT_MOVES=3
SNIFF_RANGE=4
GRENADE_RANGE=4
STEALTH_RANGE=2

ROAD='.'
PATH=' '
WALL='#'
SMOKE_GRENADE='*'



class BoardPosition():
    D_LOOKUP=['E','N','W','S']

    @staticmethod
    def str2rcd(index):
        if len(index) == 0:
            c = -1
            r = -1
            d = -1
        else:
            c = ord(index[0].upper()) - FIRST_COL
            # handle if direction is specified in string
            try:
                d = BoardPosition.D_LOOKUP.index(index[-1].upper())
            except:
                d = -1
                r = int(index[1:]) - FIRST_ROW
            else:
                r = int(index[1:-1]) - FIRST_ROW
        return r,c,d

    def  __init__(self, r=-1, c=-1, d=-1):
        self.row = r
        self.col = c
        self.d   = d

    @classmethod
    def from_string(cls, index):
        r,c,d = BoardPosition.str2rcd(index)
        return BoardPosition(r,c,d)

    @classmethod
    def clone(cls, other):
        r = other.row
        c = other.col
        d = other.d
        return BoardPosition(r,c,d)

    def __str__(self):
        if self.on_board():
            return chr(self.col + FIRST_COL) + str(self.row + FIRST_ROW) + ('' if self.d == -1 else self.D_LOOKUP[self.d])
        else:
            return "??"

    def __eq__(self,rhs):
        return self.row == rhs.row and self.col == rhs.col

    def set(self, index):
        r,c,d = BoardPosition.str2rcd(index)
        self.row = r
        self.col = c
        self.d   = d

    def on_board(self):
        return self.col >=0 and self.col < N_COLS and self.row >= 0 and self.row < N_ROWS

    def screen_pos(self):
        if self.on_board():
            y=self.row*DROW+ROWS[0]
            x=self.col*DCOL+COLS[0]
            return y,x
        else:
            return 0,0

    # return true if self is east of rhs
    def east_of(self,rhs):
        return self.col > rhs.col

    # return true if self is west of rhs
    def west_of(self,rhs):
        return self.col < rhs.col

    # return true if self is north of rhs
    def north_of(self,rhs):
        return self.row < rhs.row

    # return true if self is south of rhs
    def south_of(self,rhs):
        return self.row > rhs.row

    # return the "distance" between two positions, which is the max of
    #  the row and column differences
    def dist(self,other):
        return max([abs(self.row - other.row), abs(self.col - other.col)])


class Board():
    def __init__(self,init_empty=False):
        self.smokep = None
        self.board_cells = [[0 for c in range(N_COLS)] for r in range(N_ROWS)]
        self.backup = [[0 for c in range(N_COLS)] for r in range(N_ROWS)]
        if not init_empty:
          with open('board.csv','rt') as fd:
              board_reader = csv.reader(fd)
              r = 0
              for row in board_reader:
                  for c,val in enumerate(row):
                      self.board_cells[r][c] = val
                      self.backup[r][c] = val
                  r += 1

    def get(self, bp):
        return self.board_cells[bp.row][bp.col]

    def set(self, bp, val):
        self.board_cells[bp.row][bp.col] = val

    def place_smoke(self, bp):
        self.smokep = bp
        adj = self.adjacent(bp, only_passable=True)
        for p in adj:
            self.set(bp, SMOKE_GRENADE)

    def clear_smoke(self):
        adj = self.adjacent(bp, only_passable=True)
        for p in adj:
            self.set(bp, self.backup[p.row][p.col])
        self.smokep = None

    def contains(self, bp):
        return bp.col >=0 and bp.col < N_COLS and bp.row >= 0 and bp.row < N_ROWS

    def is_road(self, bp):
        cell = self.get(bp)
        return cell == ROAD

    def is_passable(self, bp):
        cell = self.get(bp)
        return cell == ROAD or cell == PATH or cell == SMOKE_GRENADE

    def is_wall(self, bp):
        cell = self.get(bp)
        return cell == WALL

    def is_transparent(self, bp):
        cell = self.get(bp)
        return cell == ROAD or cell == PATH

    def is_objective(self, bp):
        cell = self.get(bp)
        return cell >= 'a' and cell <= 'z'

    # returns list of positions adjacent to bp, with the optional condition they must be passable
    def adjacent(self, bp, dist=1, only_passable=False):
        n=[]
        for r in range(bp.row-dist, bp.row+dist+1):
            for c in range(bp.col-dist, bp.col+dist+1):
                if r >= 0 and r < N_ROWS and c >= 0 and c < N_COLS and (r != bp.row or c != bp.col):
                    nbp = BoardPosition(r,c)
                    if not only_passable or self.is_passable(nbp):
                        n.append(nbp)
        return n

    def roads_connected_to(self, bp):
        rl = {'E':[],'N':[],'W':[],'S':[]} # list of board positions for e/n/w/s roads
        if self.is_road(bp):
            # travel e/w to find e/w road extent
            rp = BoardPosition(bp.row, bp.col)
            road_east_terminus = bp.col
            for c in range(bp.col+1,N_COLS):
                rp.col = c
                if self.contains(rp) and self.is_road(rp):
                    road_east_terminus=c
                else:
                    break
            road_west_terminus = bp.col
            for c in range(bp.col-1, -1, -1):
                rp.col = c
                if self.contains(rp) and self.is_road(rp):
                    road_west_terminus=c
                else:
                    break
            if road_east_terminus - road_west_terminus > 1:
                # determine which n/s adjacent is rame road (if any)
                ew_other_row = bp.row - 1
                rpe = BoardPosition(ew_other_row, road_east_terminus)
                rpw = BoardPosition(ew_other_row, road_west_terminus)
                if not (self.contains(rpe) and self.contains(rpw) and self.is_road(rpe) and self.is_road(rpw)):
                    ew_other_row = bp.row + 1
            else:
                ew_other_row = -1
            if ew_other_row != -1:
                for c in range(bp.col+1, road_east_terminus+1):
                    rl['E'].append(BoardPosition(bp.row, c))
                    rl['E'].append(BoardPosition(ew_other_row, c))
                for c in range(road_west_terminus, bp.col):
                    rl['W'].append(BoardPosition(bp.row, c))
                    rl['W'].append(BoardPosition(ew_other_row, c))

            # travel n/s to find n/s road extent
            rp = BoardPosition(bp.row, bp.col)
            road_south_terminus = bp.row
            for r in range(bp.row+1,N_ROWS):
                rp.row = r
                if self.contains(rp) and self.is_road(rp):
                    road_south_terminus=r
                else:
                    break
            road_north_terminus = bp.row
            for r in range(bp.row-1, -1, -1):
                rp.row = r
                if self.contains(rp) and self.is_road(rp):
                    road_north_terminus=r
                else:
                    break
            if road_south_terminus - road_north_terminus > 1:
                # determine which e/w adjacent is rame road (if any)
                ns_other_col = bp.col - 1
                rps = BoardPosition(road_south_terminus, ns_other_col)
                rpn = BoardPosition(road_north_terminus, ns_other_col)
                if not (self.contains(rps) and self.contains(rpn) and self.is_road(rps) and self.is_road(rpn)):
                    ns_other_col = bp.col + 1
            else:
                ns_other_col = -1
            if ns_other_col != -1:
                for r in range(road_north_terminus, bp.row):
                    rl['N'].append(BoardPosition(r, bp.col))
                    rl['N'].append(BoardPosition(r, ns_other_col))
                for r in range(bp.row+1, road_south_terminus+1):
                    rl['S'].append(BoardPosition(r, bp.col))
                    rl['S'].append(BoardPosition(r, ns_other_col))
        return rl

    def hunter_los(self, hp):
        los=[hp]

        all_roads = self.roads_connected_to(hp)

        # hunter is looking E
        if hp.d == 0 or hp.d == -1:
            # accumulate LOS along this row
            for c in range(hp.col+1, N_COLS):
                bp = BoardPosition(hp.row, c)
                if self.is_transparent(bp):
                    los.append(bp)
                else:
                    break
            if self.is_road(hp):
                for r in all_roads['E']:
                    if r.east_of(hp):
                        los.append(r)

        # hunter is looking N
        if hp.d == 1 or hp.d == -1:
            # accumulate LOS along this col
            for r in range(hp.row-1, -1, -1):
                bp = BoardPosition(r, hp.col)
                if self.is_transparent(bp):
                    los.append(bp)
                else:
                    break
            if self.is_road(hp):
                for r in all_roads['N']:
                    if r.north_of(hp):
                        los.append(r)


        # hunter is looking W
        if hp.d == 2 or hp.d == -1:
            # accumulate LOS along this row
            for c in range(hp.col-1, -1, -1):
                bp = BoardPosition(hp.row, c)
                if self.is_transparent(bp):
                    los.append(bp)
                else:
                    break
            if self.is_road(hp):
                for r in all_roads['W']:
                    if r.west_of(hp):
                        los.append(r)

        # hunter is looking S
        if hp.d == 3 or hp.d == -1:
            # accumulate LOS along this col
            for r in range(hp.row+1, N_ROWS):
                bp = BoardPosition(r, hp.col)
                if self.is_transparent(bp):
                    los.append(bp)
                else:
                    break
            if self.is_road(hp):
                for r in all_roads['S']:
                    if r.south_of(hp):
                        los.append(r)
        return los

    def print(self):
        for r in range(0,N_ROWS):
            for c in range(0,N_COLS):
                print(self.board_cells[r][c],end='')
            print()


# TODO: need a way to flip HIDDEN to SURGE or STEALTH
class Agent():
    EQUIP_UNKNOWN=-1
    EQUIP_HIDDEN=0
    EQUIP_SURGE=1
    EQUIP_STEALTH=2
    EQUIP_FLASH=3
    EQUIP_SMOKE=4
    EQUIP_UNIQUE=5

    def  __init__(self,equip_slots=5):
        self.equip_list = [self.EQUIP_UNKNOWN for i in range(equip_slots)] # INVARIANT: list[i] >= list[j] for i <= j
        self.position_history=[BoardPosition.from_string('N1')] # history[i] is where the agent ended turn i
        self.turn_history=[[BoardPosition.from_string('N1')]] # history[i] is the list of positions for turn i
                                                              # INVARIANT:
                                                              #   turn_history[i][0] == position_history[i-1]
                                                              #   turn_history[i][-1] == position_history[i]

    def __str__(self):
        retv='id: '

        retv += '\nequipment:'
        for e in self.equip_list:
            retv += ' unknown' if e == Agent.EQUIP_UNKNOWN else (
                    ' unique'  if e == Agent.EQUIP_UNIQUE else (
                    ' surge'   if e == Agent.EQUIP_SURGE else (
                    ' stealth' if e == Agent.EQUIP_STEALTH else (
                    ' flash'   if e == Agent.EQUIP_FLASH else (
                    ' smoke'   if e == Agent.EQUIP_SMOKE else 'hidden' )))))
        retv += '\npos:'
        for p in self.position_history:
            retv += ' %s' % p
        retv += '\nturns:'
        for t in self.turn_history:
            for p in t:
                retv += ' %s' % p
            retv += ' |'
        retv += '\n'
        return retv

    def clone(self,other):
        self.equip_list = [e for e in other.equip_list]
        self.position_history = [BoardPosition.clone(p) for p in other.position_history]
        self.turn_history = [[BoardPosition.clone(p) for p in h] for h in other.turn_history]

    def add_turn(self,turn):
        self.turn_history.append(turn)
        self.position_history.append(turn[-1])

    def get_turn(self,idx=-1):
        return self.turn_history[idx]

    def get_position(self,idx=-1):
        return self.position_history[idx]

    def num_equip(self,e=EQUIP_UNKNOWN):
        index = [i for i in range(len(self.equip_list)) if self.equip_list[i] == e]
        if e==Agent.EQUIP_HIDDEN:
            index2 = [i for i in range(len(self.equip_list)) if self.equip_list[i] == Agent.EQUIP_SURGE]
            index.append(index2)
            index2 = [i for i in range(len(self.equip_list)) if self.equip_list[i] == Agent.EQUIP_STEALTH]
            index.append(index2)
        return len(index)

    def set_equip(self,e):
        # determine where the equipment should go, i.e. the first UNKNOWN spot
        index = len(self.equip_list) - self.num_equip(Agent.EQUIP_UNKNOWN)
        # if there's space, and if we're not maxed on this equippment
        if index < len(self.equip_list) and self.num_equip_possible(e) > 0:
            self.equip_list[index] = e
        # keep the list in proper order
        self.equip_list.sort()

    def has_unknown_equip(self):
        return self.num_equip(Agent.EQUIP_UNKNOWN) > 0

    # return the number of possible unknown equipment cards of a given type an agent might have
    # for example, an agent known to have played "stealth field" with three remaining unknown
    #  equipments can only possibly have one more stealth field
    # or, an agent cannot have any more smoke grenades if all equipment has been identified
    def num_equip_possible(self,e):
        if e == Agent.EQUIP_UNKNOWN:
            return 0 # this isn't a real equipment type
        else:
            # determine known equipment of the given type
            cnt = self.num_equip(e)
            max_num = 2
            if e == Agent.EQUIP_UNIQUE:
                # there can only be one unique equipment card
                max_num = 1
            elif e == Agent.EQUIP_HIDDEN:
                max_num = 4
            # number of slots is smaller of total open and open of this equip type
            return min(max_num - cnt, self.num_equip(Agent.EQUIP_UNKNOWN))


def print_moves(new_moves):
    for idx,p in enumerate(new_moves):
        print(p,end='')
        if idx==len(new_moves)-2:
            print('->',end='')
        elif idx==len(new_moves)-1:
            print('')
        else:
            print('-',end='')

def print_moves_list(moves_list):
    for l in range(0, len(moves_list)):
        print('length %d:' % l)
        for m in moves_list[l]:
            print_moves(m)


class Sim():
    AGENT_UNKNOWN=-1
    AGENT_OTHER=0
    AGENT_BLUEJAY=1

    def __init__(self, in_file=None, out_file=None):
        self.board = Board()
        self.agent_id = self.AGENT_UNKNOWN
        self.equip_used = 0 # 0: none, 1: apply this propagation, 2: apply during obs and cancel at next prop
        # self.agent_list[i] is the turn history for agent i
        # self.agent_list[i][j] is the move sequence for agent i's turn j
        # self.agent_list[i][j][k] is the kth position of agent i's jth turn
        self.agent_list=[Agent()]
        self.mission_pos=[]

        if out_file is not None:
            self.fdo = open(out_file, 'wt')
        else:
            self.fdo = None

        if in_file is not None:
            self.fdi = open(in_file, 'rt')
            self.init_from_file()

    def init_from_file(self):
        for l in self.fdi:
            t = l.split()
            if len(t) == 0:
                break
            if t[0] == 'propagate':
                self.propagate()
            elif t[0] == 'spotted':
                ap=BoardPosition.from_string('' if t[1] == '??' else t[1])
                hp=BoardPosition.from_string(t[2])
                self.spotted_obs(ap, hp)
            elif t[0] == 'last_seen':
                ap=BoardPosition.from_string('' if t[1] == '??' else t[1])
                hp=BoardPosition.from_string(t[2])
                self.last_seen_obs(ap, hp)
            elif t[0] == 'motion':
                cp=BoardPosition.from_string(t[1])
                self.motion_obs(cp, t[2])
            elif t[0] == 'sniffed':
                hp=BoardPosition.from_string(t[1])
                self.sniffed_obs(hp, t[2] == 'True')
            elif t[0] == 'mission':
                mp=BoardPosition.from_string(t[1])
                self.mission_obs(mp)
            elif t[0] == 'precog':
                self.precog_obs()
            elif t[0] == 'postcog':
                ap=BoardPosition.from_string(t[1])
                self.postcog_obs(ap)
            elif t[0] == 'flash':
                gp=BoardPosition.from_string(t[1])
                self.__equip_grenade_obs(gp, Agent.EQUIP_FLASH)
            elif t[0] == 'smoke':
                gp=BoardPosition.from_string(t[1])
                self.__equip_grenade_obs(gp, Agent.EQUIP_SMOKE)
            elif t[0] == 'unique':
                self.__equip_unique_obs()
            elif t[0] == 'hidden':
                self.__equip_hidden_obs()
            elif t[0] == 'bluejay':
                self.bluejay_obs(t[1] == 'True')
            else:
                print('unknown command %s' % t[0])
                break

    def propagate(self):
        if self.fdo is not None:
            self.fdo.write('propagate\n')

        # first, clean up any smoke grenades from last turn
        if self.board.smokep is not None:
            self.board.clear_smoke()
            print('cleared smoke')

        if self.equip_used == 2:
            self.equip_used = 0

        # we don't actually care about detailed history once the hunter turn is over.
        # therefore, before propagating we can ignore any differences in how agents moved
        # between end turn locations and collapse those that have the same end history and
        # equipment lists
        #
        # as long as all observations are processed, all remaining paths are equally likely
        # for simplicity we keep the history of the first agent to reach a given position with
        # a given set of equipment
        # TODO: keep track of the "weight" of an agent, i.e. the number of equivalent paths
        #  that were collapsed. this will help us better estimate the prob distribution
        unique_list=[]
        trimmed_agents=[]
        for agent in self.agent_list:
            u = [agent.equip_list, agent.get_position()]
            # need to consider two turns to allow post-cog to work
            if len(agent.turn_history) > 1:
                u.append(agent.get_position(-2))
            try:
                unique_list.index(u)
            except:
                trimmed_agents.append(agent)
                unique_list.append(u)
        print('trimmed %d -> %d' % (len(self.agent_list), len(trimmed_agents)))
        # TODO: unique list is a good place to check for equipment that all agent particles have

        new_agents=[]
        # we're going to propagate every tracked agent to all the places they could go, each becoming a new agent
        for agent in trimmed_agents:
            # propagation starts at the last position in their history
            start_pos = agent.get_position()
            # we'll have a list for each possible move sequence length
            # length 0 consists of staying put
            n_moves_list = [[[start_pos]]]
            # num moves can depend on if the agent plays "adrenal surge"
            max_num_moves = NUM_MOVES_PER_TURN
            if self.equip_used == 1 and agent.num_equip_possible(Agent.EQUIP_SURGE) > 0:
                max_num_moves = NUM_MOVES_PER_TURN_SURGE
            for l in range(1, max_num_moves+1):
                # initialize the list for this sequence length
                n_moves_list.append([])
                # we take every sequence from the previous length and expand by one move
                for moves in n_moves_list[l-1]:
                    # grab where the sequence stopped
                    last_pos = moves[-1]
                    # compute the neighbors of that position
                    n = self.board.adjacent(last_pos, only_passable=True)
                    for j in n:
                        new_moves=moves+[j]
                        n_moves_list[l].append(new_moves)
            # now, all these new moves turn into agent particles with the same shared history
            for m in range(0, len(n_moves_list)):
                for t in n_moves_list[m]:
                    new_agent = Agent()
                    new_agent.clone(agent)
                    new_agent.add_turn(t)
                    if len(t) > NUM_MOVES_PER_TURN+1:
                        new_agent.set_equip(Agent.EQUIP_SURGE)
                    new_agents.append(new_agent)
        self.agent_list = new_agents

        if self.equip_used == 1:
            self.equip_used = 2

    # ap is the location the agent was spotted (empty if not spotted)
    # hp is the location of the observant hunter
    def spotted_obs(self, ap, hp):
        if self.fdo is not None:
            self.fdo.write('spotted %s %s\n' % (str(ap), str(hp)))
        new_list=[]
        if self.board.contains(ap):
            print('spotted from %s at %s' % (str(hp), str(ap)))
            # kepp all agents at ap
            for a in self.agent_list:
                if a.get_position() == ap:
                    new_list.append(a)
        else:
            print('not in LOS from %s' % str(hp))
            # keep all agents that are not in hunter LOS
            los = self.board.hunter_los(hp)
            for a in self.agent_list:
                try:
                    los.index(a.get_position())
                except:
                    new_list.append(a)
                else:
                    # if the agent played equipment that could have been "stealth field",
                    #  keep them if they were in the LOS but never closer than 3 spaces
                    # also, it's possible they just played "adrenal surge", in which case they
                    #  can't have played "stealth field"
                    if self.equip_used == 2 and a.num_equip_possible(Agent.EQUIP_STEALTH) > 0 and len(a.get_turn()) <= NUM_MOVES_PER_TURN+1:
                        close_pos = [p for p in a.get_turn() if p.dist(hp) <= STEALTH_RANGE]
                        if len(close_pos) == 0:
                            a.set_equip(Agent.EQUIP_STEALTH)
                            new_list.append(a)
        self.agent_list = new_list

    # ap is the location the agent was last seen (empty if not seen)
    # hp is the location of the observant hunter
    def last_seen_obs(self, ap, hp):
        if self.fdo is not None:
            self.fdo.write('last_seen %s %s\n' % (str(ap), str(hp)))
        new_list=[]
        los = self.board.hunter_los(hp)
        if self.board.contains(ap):
            print('last seen from %s at %s' % (str(hp), str(ap)))
            for a in self.agent_list:
                #  keep agents that passed through ap and didn't end in ap and weren't visible
                #  through a later LOS
                idx = [i for i,v in enumerate(a.get_turn()[:-1]) if v == ap]
                #  agent passed through ap so they definitely were spotted
                if len(idx) > 0:
                    # now for the moves after where the agent last passed through ap, make sure none
                    #  are in the hunter LOS
                    idx = idx[-1]
                    later_los=False
                    for p in a.get_turn()[idx+1:]:
                        try:
                            los.index(p)
                        except:
                            pass
                        else:
                            later_los = True
                            break
                    if not later_los:
                        new_list.append(a)
                # if the agent could be bluejay and has not played their unique ability card
                #  then create a clone of this agent who has played "holo decoy" and keep them
                #  anyway
                # TODO: remember that last seen will positively identify the agent!
                if self.agent_id != self.AGENT_OTHER and a.num_equip_possible(Agent.EQUIP_UNIQUE) > 0:
                    b = Agent()
                    b.clone(a)
                    b.set_equip(Agent.EQUIP_UNIQUE)
                    new_list.append(b)
        else:
            print('not seen crossing LOS of %s' % str(hp))
            # keep agents that didn't cross LOS, or agents that played equipment that could have
            #  used "stealth field"
            for a in self.agent_list:
                in_los=False
                for p in a.get_turn():
                    try:
                        los.index(p)
                    except:
                        pass
                    else:
                        in_los=True
                        break
                if not in_los:
                    new_list.append(a)
                elif self.equip_used == 2 and a.num_equip_possible(Agent.EQUIP_STEALTH) > 0:
                    # if the agent could have played "stealth field", keep them if they were
                    # never closer than 3 spaces
                    close_pos = [p for p in a.get_turn() if p.dist(hp) <= STEALTH_RANGE]
                    if len(close_pos) == 0:
                        a.set_equip(Agent.EQUIP_STEALTH)
                        new_list.append(a)
        self.agent_list = new_list

    # mp is the location of the completed mission objective
    def mission_obs(self, mp):
        if self.fdo is not None:
            self.fdo.write('mission %s\n' % str(mp))
        print('misson %s' % str(mp))
        self.mission_pos.append(mp)
        # keep agents that started adjacent to the mission objective
        new_list=[]
        # if agent is known to not be bluejay, agent must have started within one space of the objective
        # otherwise, they could have started within two spaces
        if self.agent_id == self.AGENT_OTHER:
            adj = self.board.adjacent(mp, only_passable=True)
        else:
            adj = self.board.adjacent(mp,dist=2, only_passable=True)
        for a in self.agent_list:
            # try looking for where they started their turn in the positions next to the objective
            try:
                adj.index(a.get_turn()[0])
            except:
                pass
            else:
                new_list.append(a)
        self.agent_list = new_list

    # cp is the location of the car
    # d is either the direction motion was detected (e.g. NW, E, etc) or empty string for no motion
    def motion_obs(self, cp, d):
        if self.fdo is not None:
            self.fdo.write('motion %s %s\n' % (str(cp), d))
        new_list=[]
        if d == 'none':
            print('no motion')
            # keep all agents whose last turn pos list length is less than motion detect thresh
            for a in self.agent_list:
                if len(a.get_turn()) < MOTION_DETECT_MOVES + 1:
                    new_list.append(a)
        else:
            print('motion to the %s of %s' % (d, str(cp)))
            # keep all agents in the given direction and whose last turn pos list length
            #   is greater than motion detect thresh
            if d == 'E':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row == cp.row and ap.col > cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'NE':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row < cp.row and ap.col > cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'N':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.col == cp.col and ap.row < cp.row and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'NW':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row < cp.row and ap.col < cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'W':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row == cp.row and ap.col < cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'SW':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row > cp.row and ap.col < cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'S':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.col == cp.col and ap.row > cp.row and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            elif d == 'SE':
                for a in self.agent_list:
                    ap = a.get_position()
                    if ap.row > cp.row and ap.col > cp.col and len(a.get_turn()) >= MOTION_DETECT_MOVES + 1:
                        new_list.append(a)
            else:
                pass
        self.agent_list = new_list

    # hp is the location of the hunter (beast)
    # sniffed is true if the agent was detected, false otherwise
    def sniffed_obs(self, hp, sniffed):
        if self.fdo is not None:
            self.fdo.write('sniffed %s %s\n' % (str(hp), 'True' if sniffed else 'False'))
        new_list=[]
        if sniffed:
            print('sniffed near %s' % str(hp))
            # keep all agents within 4 spaces of hp
            for a in self.agent_list:
                ap = a.get_position()
                if abs(ap.row - hp.row) <= SNIFF_RANGE and abs(ap.col - hp.col) <= SNIFF_RANGE:
                    new_list.append(a)
        else:
            print('not sniffed near %s' % str(hp))
            # keep all agents not within 4 spaces of hp
            for a in self.agent_list:
                ap = a.get_position()
                if abs(ap.row - hp.row) > SNIFF_RANGE or abs(ap.col - hp.col) > SNIFF_RANGE:
                    new_list.append(a)
        self.agent_list = new_list

    def precog_obs(self):
        if self.fdo is not None:
            self.fdo.write('precog\n')
        print('precog')
        # only keep agents adjacent to any mission objective
        new_list=[]
        for a in self.agent_list:
            # if agent is known to not be bluejay, agent must have ended within one space of the objective
            # otherwise, they could have ended within two spaces
            if self.agent_id == self.AGENT_OTHER:
                adj = self.board.adjacent(a.get_position())
            else:
                adj = self.board.adjacent(a.get_position(), dist=2)
            for p in adj:
                if self.board.is_objective(p):
                    new_list.append(a)
                    break
        self.agent_list = new_list

    # ap is the location of the agent two turns ago
    def postcog_obs(self, ap):
        if self.fdo is not None:
            self.fdo.write('postcog %s\n' % (ap))
        print('postcog at %s' % str(ap))
        new_list=[]
        # only keep agents who were at ap two turns ago
        for a in self.agent_list:
            if a.get_turn(-3)[-1] == ap:
                new_list.append(a)
        self.agent_list = new_list

    def __equip_grenade_obs(self, gp, g_type):
        if g_type == Agent.EQUIP_FLASH:
            if self.fdo is not None:
                self.fdo.write('flash %s\n' % (gp))
            print('flash grenade at %s' % str(gp))
        elif g_type == Agent.EQUIP_SMOKE:
            if self.fdo is not None:
                self.fdo.write('smoke %s\n' % (gp))
            print('smoke grenade at %s' % str(gp))
            self.board.place_smoke(gp)
        new_list=[]
        # only keep agents that have an unused equipment slot, and were within
        #  4 spaces of the grenade location at any point during their last turn
        # also, note the equipment
        for a in self.agent_list:
            if a.num_equip_possible(g_type) > 0:
                for p in a.get_turn():
                    if abs(p.row - gp.row) <= GRENADE_RANGE and abs(p.col - gp.col) <= GRENADE_RANGE:
                        a.set_equip(g_type)
                        new_list.append(a)
                        break
        self.agent_list = new_list

    def __equip_unique_obs(self):
        if self.fdo is not None:
            self.fdo.write('unique\n')
        print('agent\'s unique equipment used')
        # keep agents that have an unused equipment slot and note the unique equipment
        new_list=[]
        for a in self.agent_list:
            if a.num_equip_possible(Agent.EQUIP_UNIQUE) > 0:
                a.set_equip(Agent.EQUIP_UNIQUE)
                new_list.append(a)
        self.agent_list = new_list

    def __equip_hidden_obs(self):
        if self.fdo is not None:
            self.fdo.write('hidden\n')
        print('hidden equipment used')
        # note that some hidden equipment was used
        self.equip_used = 1
        # keep agents that have an unused equipment slot and note in the agent the hidden equipment
        new_list=[]
        for a in self.agent_list:
            if a.num_equip_possible(Agent.EQUIP_HIDDEN) > 0:
                a.set_equip(Agent.EQUIP_HIDDEN)
                new_list.append(a)
        self.agent_list = new_list

    def equip_obs(self, ep, e_type):
        if e_type == Agent.EQUIP_FLASH or e_type == Agent.EQUIP_SMOKE:
            self.__equip_grenade_obs(ep, e_type)
        elif e_type == Agent.EQUIP_UNIQUE:
            self.__equip_unique_obs()
        else:
            self.__equip_hidden_obs()

    def bluejay_obs(self, is_bluejay):
        if self.fdo is not None:
            self.fdo.write('bluejay %s\n' % ('True' if is_bluejay else 'False'))
        if is_bluejay:
            print('id: bluejay')
            self.agent_id = self.AGENT_BLUEJAY
        else:
            print('id: not bluejay')
            self.agent_id = self.AGENT_OTHER


class MainWindow(tk.Frame):
    def __init__(self, in_file=None, out_file=None, master=None):
        tk.Frame.__init__(self, master)
        self.grid()

        self.sim = Sim(in_file=in_file, out_file=out_file)

        self.init_ui()
        self.winfo_toplevel().title("Specter Ops Agent Locator")

        #self.draw_test()
        self.draw_probability()

    def init_ui(self):
        # TODO: it would be nice to show known info, i.e. bluejay or not, used equip
        self.canvas = tk.Canvas(self, width=570,height=800)
        self.canvas.grid(column=0, row=0, rowspan=30)
        self.board_img = ImageTk.PhotoImage(Image.open("board.png"))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.board_img)
        self.prob_grid=[]
        self.inspect_path=[]

        entry_row=0
        self.propagate_button = tk.Button(self, text="Propagate", command=self.on_prop_click)
        self.propagate_button.grid(column=1, row=entry_row)
        self.agent_count_text = tk.StringVar()
        self.agent_count_text.set('Agents: 1')
        self.agent_count = tk.Label(self, textvariable=self.agent_count_text)
        self.agent_count.grid(column=2, row=entry_row)
        entry_row += 1

        self.inspect_button = tk.Button(self, text="Inspect", command=self.on_inspect_click)
        self.inspect_button.grid(column=1, row=entry_row)
        self.inspect_entry_text = tk.StringVar()
        self.inspect_entry_text.set('0')
        self.inspect_entry = tk.Entry(self, textvariable=self.inspect_entry_text)
        self.inspect_entry.grid(column=2, row=entry_row)
        entry_row += 1

        def bluejay_true_click(self=self, res=True):
            return self.on_bluejay_click(res)
        def bluejay_false_click(self=self, res=False):
            return self.on_bluejay_click(res)
        self.bluejayt_button = tk.Button(self, text="Bluejay: true", command=bluejay_true_click)
        self.bluejayt_button.grid(column=1, row=entry_row)
        self.bluejayf_button = tk.Button(self, text="Bluejay: false", command=bluejay_false_click)
        self.bluejayf_button.grid(column=2, row=entry_row)
        entry_row += 1

        self.spotted_button = tk.Button(self, text="Spotted", command=self.on_spotted_click)
        self.spotted_button.grid(column=1, row=entry_row)
        self.last_seen_button = tk.Button(self, text="Last seen", command=self.on_last_seen_click)
        self.last_seen_button.grid(column=2, row=entry_row)
        entry_row += 1

        self.mission_button = tk.Button(self, text="Mission", command=self.on_mission_click)
        self.mission_button.grid(column=1, row=entry_row, columnspan=2)
        entry_row += 1

        def flash_grenade_click(self=self, e_type=Agent.EQUIP_FLASH):
            return self.on_equip_click(e_type)
        def smoke_grenade_click(self=self, e_type=Agent.EQUIP_SMOKE):
            return self.on_equip_click(e_type)
        def unique_equip_click(self=self, e_type=Agent.EQUIP_UNIQUE):
            return self.on_equip_click(e_type)
        def hidden_equip_click(self=self, e_type=Agent.EQUIP_HIDDEN):
            return self.on_equip_click(e_type)
        self.flash_grenade_button = tk.Button(self, text="Flash grenade", command=flash_grenade_click)
        self.flash_grenade_button.grid(column=1, row=entry_row)
        self.smoke_grenade_button = tk.Button(self, text="Smoke grenade", command=smoke_grenade_click)
        self.smoke_grenade_button.grid(column=2, row=entry_row)
        entry_row += 1
        self.unique_equip_button = tk.Button(self, text="Unique equipment", command=unique_equip_click)
        self.unique_equip_button.grid(column=1, row=entry_row)
        self.hidden_equip_button = tk.Button(self, text="Hidden equipment", command=hidden_equip_click)
        self.hidden_equip_button.grid(column=2, row=entry_row)
        entry_row += 1

        sub_frame = tk.Frame(self)
        sub_frame.grid(column=1, row=entry_row, columnspan=2)
        entry_row += 1
        def nw_motion_click(self=self, mot='NW'):
            return self.on_motion_click(mot)
        self.motion_nw_button = tk.Button(sub_frame, text="NW", command=nw_motion_click)
        self.motion_nw_button.grid(column=0, row=0)
        def n_motion_click(self=self, mot='N'):
            return self.on_motion_click(mot)
        self.motion_n_button = tk.Button(sub_frame, text="N", command=n_motion_click)
        self.motion_n_button.grid(column=1, row=0)
        def ne_motion_click(self=self, mot='NE'):
            return self.on_motion_click(mot)
        self.motion_ne_button = tk.Button(sub_frame, text="NE", command=ne_motion_click)
        self.motion_ne_button.grid(column=2, row=0)
        def w_motion_click(self=self, mot='W'):
            return self.on_motion_click(mot)
        self.motion_w_button = tk.Button(sub_frame, text="W", command=w_motion_click)
        self.motion_w_button.grid(column=0, row=1)
        def no_motion_click(self=self, mot=''):
            return self.on_motion_click(mot)
        self.motion_no_button = tk.Button(sub_frame, text="No Motion", command=no_motion_click)
        self.motion_no_button.grid(column=1, row=1)
        def e_motion_click(self=self, mot='E'):
            return self.on_motion_click(mot)
        self.motion_e_button = tk.Button(sub_frame, text="E", command=e_motion_click)
        self.motion_e_button.grid(column=2, row=1)
        def sw_motion_click(self=self, mot='SW'):
            return self.on_motion_click(mot)
        self.motion_sw_button = tk.Button(sub_frame, text="SW", command=sw_motion_click)
        self.motion_sw_button.grid(column=0, row=2)
        def s_motion_click(self=self, mot='S'):
            return self.on_motion_click(mot)
        self.motion_s_button = tk.Button(sub_frame, text="S", command=s_motion_click)
        self.motion_s_button.grid(column=1, row=2)
        def se_motion_click(self=self, mot='SE'):
            return self.on_motion_click(mot)
        self.motion_se_button = tk.Button(sub_frame, text="SE", command=se_motion_click)
        self.motion_se_button.grid(column=2, row=2)

        def sniffed_true_click(self=self, res=True):
            return self.on_sniffed_click(res)
        def sniffed_false_click(self=self, res=False):
            return self.on_sniffed_click(res)
        self.sniffedt_button = tk.Button(self, text="Sniffed: true", command=sniffed_true_click)
        self.sniffedt_button.grid(column=1, row=entry_row)
        self.sniffedf_button = tk.Button(self, text="Sniffed: false", command=sniffed_false_click)
        self.sniffedf_button.grid(column=2, row=entry_row)
        entry_row += 1

        self.precog_button = tk.Button(self, text="Pre-cognition", command=self.on_precog_click)
        self.precog_button.grid(column=1, row=entry_row)
        self.postcog_button = tk.Button(self, text="Post-cognition", command=self.on_postcog_click)
        self.postcog_button.grid(column=2, row=entry_row)
        entry_row += 1

        l=tk.Label(self, text="Agent pos")
        l.grid(column=1, row=entry_row)
        self.agent_pos_entry_text = tk.StringVar()
        self.agent_pos_entry_text.set('N1')
        self.agent_pos_entry = tk.Entry(self, textvariable=self.agent_pos_entry_text)
        self.agent_pos_entry.grid(column=2, row=entry_row)
        entry_row += 1
        l=tk.Label(self, text="Hunter pos")
        l.grid(column=1, row=entry_row)
        self.hunter_pos_entry_text = tk.StringVar()
        self.hunter_pos_entry_text.set('K23')
        self.hunter_pos_entry = tk.Entry(self, textvariable=self.hunter_pos_entry_text)
        self.hunter_pos_entry.grid(column=2, row=entry_row)
        entry_row += 1
        l=tk.Label(self, text="Extra info")
        l.grid(column=1, row=entry_row)
        self.extra_entry_text = tk.StringVar()
        self.extra_entry_text.set('')
        self.extra_entry = tk.Entry(self, textvariable=self.extra_entry_text)
        self.extra_entry.grid(column=2, row=entry_row)
        entry_row += 1

        self.tooltip_display = tk.Text(self, wrap=tk.WORD, height=10, width=60)
        self.tooltip_display.grid(column=1, row=entry_row, columnspan=2)
        entry_row += 1

        self.los_test_button = tk.Button(self, text="LOS test", command=self.on_los_test_click)
        self.los_test_button.grid(column=1, row=entry_row, columnspan=2)
        entry_row += 1

        self.reset_button = tk.Button(self, text="RESET", command=self.on_reset_click)
        self.reset_button.grid(column=1, row=entry_row, columnspan=2)
        entry_row += 1

        # tooltips
        def ttp_clear(event, self=self, text=''):
            return self.tooltip_text(text)
        def propagate_button_ttp(event, self=self, text='Take all hypothetical agents and compute all possible locations one turn later.'):
            return self.tooltip_text(text)
        def agent_count_ttp(event, self=self, text='Number of hypothetical agents being tracked.'):
            return self.tooltip_text(text)
        def inspect_ttp(event, self=self, text='Plot the route of an agent, indexed by the number in the entry box.'):
            return self.tooltip_text(text)
        def bluejay_button_ttp(event, self=self, text='If the agent is positively identified, click the true/false button depending on if the agent is Bluejay or not. Do this before providing spotted or last seen observations.'):
            return self.tooltip_text(text)
        def spotted_button_ttp(event, self=self, text='Enter the location of the hunter in the hunter pos entry box, and enter the location of the agent in the agent pos entry box. Or, if the hunter did not spot the agent, leave the agent position blank. If the agent is not spotted, you can enter multiple hunter locations, separated by spaces.'):
            return self.tooltip_text(text)
        def last_seen_button_ttp(event, self=self, text='Enter the location of the hunter in the hunter pos entry box, and enter the location where the agent was last seen in the agent pos entry box. Or, if there was no last seen marker, leave the agent position blank. If the agent is not spotted, you can enter multiple hunter locations, separated by spaces.'):
            return self.tooltip_text(text)
        def mission_button_ttp(event, self=self, text='If an agent completes a mission objective, enter the objective location in the agent pos entry box and click this button.'):
            return self.tooltip_text(text)
        def grenade_button_ttp(event, self=self, text='If the agent plays a grenade, enter the grenade location in the agent pos entry box, and click the grenade type button immediately after propagation and before any other observations are made.\n\nA smoke grenade is cleared on the next propagation.\n\nProvide only spotted (not last seen) positive or negative observations for flash blinded hunters.'):
            return self.tooltip_text(text)
        def unique_equip_button_ttp(event, self=self, text='Click if the agent plays their role-specific equipment card.'):
            return self.tooltip_text(text)
        def hidden_equip_button_ttp(event, self=self, text='Click if the agent plays non-reveal equipment during their turn. Be sure to do this before clicking Propagate!'):
            return self.tooltip_text(text)
        def motion_button_ttp(event, self=self, text='If the vehicle\'s motion sensor was used, click the direction the agent was detected, or click No Motion if the agent was not detected.'):
            return self.tooltip_text(text)
        def sniffed_button_ttp(event, self=self, text='If the Beast\'s enhanced senses were used, enter the hunter location in the hunter pos entry box, and click the true/false button depending on if the agent was sensed or not.'):
            return self.tooltip_text(text)
        def precog_button_ttp(event, self=self, text='Click if the Prophet\'s pre-cognition was used.'):
            return self.tooltip_text(text)
        def postcog_button_ttp(event, self=self, text='If the Prophet\'s post-cognision was used, enter the location where the agent was two turns ago in the agent pos entry box.'):
            return self.tooltip_text(text)
        def agent_pos_ttp(event, self=self, text='Supply agent position here for observations that require it.'):
            return self.tooltip_text(text)
        def hunter_pos_ttp(event, self=self, text='Supply hunter position here for observations that require it.'):
            return self.tooltip_text(text)
        def extra_entry_ttp(event, self=self, text='Supply extra information here for observations that require it.'):
            return self.tooltip_text(text)
        self.propagate_button.bind(    '<Enter>', propagate_button_ttp)
        self.agent_count.bind(         '<Enter>', agent_count_ttp)
        self.inspect_button.bind(      '<Enter>', inspect_ttp)
        self.inspect_entry.bind(       '<Enter>', inspect_ttp)
        self.bluejayt_button.bind(     '<Enter>', bluejay_button_ttp)
        self.bluejayf_button.bind(     '<Enter>', bluejay_button_ttp)
        self.spotted_button.bind(      '<Enter>', spotted_button_ttp)
        self.last_seen_button.bind(    '<Enter>', last_seen_button_ttp)
        self.flash_grenade_button.bind('<Enter>', grenade_button_ttp)
        self.smoke_grenade_button.bind('<Enter>', grenade_button_ttp)
        self.unique_equip_button.bind( '<Enter>', unique_equip_button_ttp)
        self.hidden_equip_button.bind( '<Enter>', hidden_equip_button_ttp)
        self.mission_button.bind(      '<Enter>', mission_button_ttp)
        self.motion_nw_button.bind(    '<Enter>', motion_button_ttp)
        self.motion_n_button.bind(     '<Enter>', motion_button_ttp)
        self.motion_ne_button.bind(    '<Enter>', motion_button_ttp)
        self.motion_w_button.bind(     '<Enter>', motion_button_ttp)
        self.motion_no_button.bind(    '<Enter>', motion_button_ttp)
        self.motion_e_button.bind(     '<Enter>', motion_button_ttp)
        self.motion_sw_button.bind(    '<Enter>', motion_button_ttp)
        self.motion_s_button.bind(     '<Enter>', motion_button_ttp)
        self.motion_se_button.bind(    '<Enter>', motion_button_ttp)
        self.sniffedt_button.bind(     '<Enter>', sniffed_button_ttp)
        self.sniffedf_button.bind(     '<Enter>', sniffed_button_ttp)
        self.precog_button.bind(       '<Enter>', precog_button_ttp)
        self.postcog_button.bind(      '<Enter>', postcog_button_ttp)
        self.agent_pos_entry.bind(     '<Enter>', agent_pos_ttp)
        self.hunter_pos_entry.bind(    '<Enter>', hunter_pos_ttp)
        self.extra_entry.bind(         '<Enter>', extra_entry_ttp)
        self.propagate_button.bind(    '<Leave>', ttp_clear)
        self.agent_count.bind(         '<Leave>', ttp_clear)
        self.inspect_button.bind(      '<Leave>', ttp_clear)
        self.inspect_entry.bind(       '<Leave>', ttp_clear)
        self.bluejayt_button.bind(     '<Leave>', ttp_clear)
        self.bluejayf_button.bind(     '<Leave>', ttp_clear)
        self.spotted_button.bind(      '<Leave>', ttp_clear)
        self.last_seen_button.bind(    '<Leave>', ttp_clear)
        self.flash_grenade_button.bind('<Leave>', ttp_clear)
        self.smoke_grenade_button.bind('<Leave>', ttp_clear)
        self.unique_equip_button.bind( '<Leave>', ttp_clear)
        self.hidden_equip_button.bind( '<Leave>', ttp_clear)
        self.mission_button.bind(      '<Leave>', ttp_clear)
        self.motion_nw_button.bind(    '<Leave>', ttp_clear)
        self.motion_n_button.bind(     '<Leave>', ttp_clear)
        self.motion_ne_button.bind(    '<Leave>', ttp_clear)
        self.motion_w_button.bind(     '<Leave>', ttp_clear)
        self.motion_no_button.bind(    '<Leave>', ttp_clear)
        self.motion_e_button.bind(     '<Leave>', ttp_clear)
        self.motion_sw_button.bind(    '<Leave>', ttp_clear)
        self.motion_s_button.bind(     '<Leave>', ttp_clear)
        self.motion_se_button.bind(    '<Leave>', ttp_clear)
        self.sniffedt_button.bind(     '<Leave>', ttp_clear)
        self.sniffedf_button.bind(     '<Leave>', ttp_clear)
        self.precog_button.bind(       '<Leave>', ttp_clear)
        self.postcog_button.bind(      '<Leave>', ttp_clear)
        self.agent_pos_entry.bind(     '<Leave>', ttp_clear)
        self.hunter_pos_entry.bind(    '<Leave>', ttp_clear)
        self.extra_entry.bind(         '<Leave>', ttp_clear)

    def draw_probability(self):
        self.agent_count_text.set('Agents: %d' % len(self.sim.agent_list))
        for i in self.inspect_path:
            self.canvas.delete(i)
        for i in self.prob_grid:
            self.canvas.delete(i)
        for p in self.sim.mission_pos:
            sp=p.screen_pos()
            self.prob_grid.append(self.canvas.create_polygon(sp[1]-DCOL/2+PROB_RECT_OFFSET,sp[0]-DROW/2+PROB_RECT_OFFSET,
                                                             sp[1]+DCOL/2-PROB_RECT_OFFSET,sp[0]-DROW/2+PROB_RECT_OFFSET,
                                                             sp[1],sp[0]+DROW/2-PROB_RECT_OFFSET,
                                                             fill='',outline='red',width=3))
        prob_board = Board(init_empty = True)
        num_agent = len(self.sim.agent_list)
        for agent in self.sim.agent_list:
            pos = agent.get_position()
            tmp = prob_board.get(pos)
            prob_board.set(pos, tmp + 1.0 / num_agent)
        for r in range(0,N_ROWS):
            for c in range(0,N_COLS):
                p = prob_board.board_cells[r][c]
                if p > 0:
                    gc=BoardPosition(r,c).screen_pos()
                    b = int(p*2550)
                    b = b if b < 255 else 255
                    g = int((p-0.1)/0.9*255)
                    g = g if g > 0 else 0
                    color='#00%02x%02x' % (g, b)
                    self.prob_grid.append(self.canvas.create_rectangle(gc[1]-DCOL/2+PROB_RECT_OFFSET,gc[0]-DROW/2+PROB_RECT_OFFSET,gc[1]+DCOL/2-PROB_RECT_OFFSET,gc[0]+DROW/2-PROB_RECT_OFFSET,fill='',outline=color,width=3))

    def draw_test(self):
        for r in range(0,N_ROWS):
            for c in range(0,N_COLS):
                bp=BoardPosition(r,c)
                if self.sim.board.is_passable(bp):
                    gc=[r*DROW+ROWS[0], c*DCOL+COLS[0]]
                    self.prob_grid.append(self.canvas.create_rectangle(gc[1]-DCOL/2+PROB_RECT_OFFSET,gc[0]-DROW/2+PROB_RECT_OFFSET,gc[1]+DCOL/2-PROB_RECT_OFFSET,gc[0]+DROW/2-PROB_RECT_OFFSET,outline='#00ff00',width=3))
        for t in range(1,N_TURNS+1):
            self.prob_grid.append(self.canvas.create_text(TURNS_COL, t * DTURN + TURNS_ROW[0], text=str(t)))

    def main(self):
        self.root.mainloop()

    def on_prop_click(self):
        self.sim.propagate()
        self.draw_probability()

    def on_inspect_click(self):
        if len(self.inspect_entry.get()) == 0:
            self.draw_probability()
            return

        try:
            index = int(self.inspect_entry.get())
        except:
            return

        if index < 0 or index >= len(self.sim.agent_list):
            return

        for i in self.inspect_path:
            self.canvas.delete(i)
        for i,h in enumerate(self.sim.agent_list[index].turn_history):
            for j,p in enumerate(h):
                this_p=p.screen_pos()
                if j == len(h)-1:
                    color = 'red'
                    if i > 0:
                        self.inspect_path.append(self.canvas.create_text(TURNS_COL, i * DTURN + TURNS_ROW[0], text=str(p)))
                else:
                    color = 'green'
                if i > 0 and j == 0:
                    continue
                if i != 0 or j != 0:
                    self.inspect_path.append(self.canvas.create_line(last_p[1], last_p[0], this_p[1], this_p[0], fill='green'))
                self.inspect_path.append(self.canvas.create_oval(this_p[1]-DCOL/2+PROB_RECT_OFFSET,
                                                                this_p[0]-DROW/2+PROB_RECT_OFFSET,
                                                                this_p[1]+DCOL/2-PROB_RECT_OFFSET,
                                                                this_p[0]+DROW/2-PROB_RECT_OFFSET,
                                                                outline=color))
                last_p=this_p

    def on_spotted_click(self):
        ap=BoardPosition.from_string(self.agent_pos_entry_text.get())
        hp=BoardPosition()
        for p in self.hunter_pos_entry_text.get().split():
            hp.set(p)
            self.sim.spotted_obs(ap, hp)
        self.draw_probability()

    def on_last_seen_click(self):
        ap=BoardPosition.from_string(self.agent_pos_entry_text.get())
        hp=BoardPosition()
        for p in self.hunter_pos_entry_text.get().split():
            hp.set(p)
            self.sim.last_seen_obs(ap, hp)
        self.draw_probability()

    def on_mission_click(self):
        mp=BoardPosition.from_string(self.agent_pos_entry_text.get())
        self.sim.mission_obs(mp)
        self.draw_probability()

    def on_motion_click(self, mot):
        cp=BoardPosition.from_string(self.hunter_pos_entry_text.get())
        self.sim.motion_obs(cp, 'none' if mot == '' else mot)
        self.draw_probability()

    def on_sniffed_click(self, res):
        hp=BoardPosition.from_string(self.hunter_pos_entry_text.get())
        self.sim.sniffed_obs(hp, res)
        self.draw_probability()

    def on_precog_click(self):
        self.sim.precog_obs()
        self.draw_probability()

    def on_postcog_click(self):
        ap=BoardPosition.from_string(self.agent_pos_entry_text.get())
        self.sim.postcog_obs(ap)
        self.draw_probability()

    def on_equip_click(self, g_type):
        ap=BoardPosition.from_string(self.agent_pos_entry_text.get())
        self.sim.equip_obs(ap, g_type)
        self.draw_probability()

    def on_bluejay_click(self, res):
        self.sim.bluejay_obs(res)
        self.draw_probability()

    def on_los_test_click(self):
        for i in self.inspect_path:
            self.canvas.delete(i)
        hp=BoardPosition.from_string(self.hunter_pos_entry_text.get())
        los = self.sim.board.hunter_los(hp)
        for p in los:
            this_p=p.screen_pos()
            self.inspect_path.append(self.canvas.create_oval(this_p[1]-DCOL/2+PROB_RECT_OFFSET,
                                                             this_p[0]-DROW/2+PROB_RECT_OFFSET,
                                                             this_p[1]+DCOL/2-PROB_RECT_OFFSET,
                                                             this_p[0]+DROW/2-PROB_RECT_OFFSET,
                                                             outline='yellow'))
        this_p=hp.screen_pos()
        self.inspect_path.append(self.canvas.create_oval(this_p[1]-DCOL/2+PROB_RECT_OFFSET,
                                                         this_p[0]-DROW/2+PROB_RECT_OFFSET,
                                                         this_p[1]+DCOL/2-PROB_RECT_OFFSET,
                                                         this_p[0]+DROW/2-PROB_RECT_OFFSET,
                                                         outline='purple'))

    def on_reset_click(self):
        self.sim = Sim()
        self.draw_probability()

    def tooltip_text(self, text):
        self.tooltip_display.delete('1.0', 'end')
        self.tooltip_display.insert('1.0', text)


def main(argv):
    parser = argparse.ArgumentParser(description='Specter ops agent location modelling')
    parser.add_argument( '--input',  help='Initialize state based on saved log file', default=None )
    parser.add_argument( '--output', help='Log user input to text file',              default=None )

    main_args = parser.parse_args()

    app = MainWindow(in_file=main_args.input, out_file=main_args.output)
    app.mainloop()


if __name__ == "__main__":
    main(sys.argv[1:])

