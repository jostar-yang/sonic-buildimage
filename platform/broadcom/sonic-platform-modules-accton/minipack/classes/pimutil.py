#!/usr/bin/env python
#
# Copyright (C) 2019 Accton Technology Corporation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ------------------------------------------------------------------
# HISTORY:
#    mm/dd/yyyy (A.D.)
#    5/29/2019:  Jostar create for minipack
# -----------------------------------------------------------
try:
    import os
    import sys, getopt
    import subprocess
    import click
    import imp
    import logging
    import logging.config
    import logging.handlers
    import types
    import time  # this is only being used as part of the example
    import traceback
    from tabulate import tabulate
    import fbfpgaio
    import re
    import time
    from select import select
    #from ctypes import fbfpgaio 

except ImportError as e:
    raise ImportError('%s - required module not found' % str(e))


# pimutil.py
#
# Platform-specific PIM interface for SONiC
#

iob = {
    "revision": 0x0,
    "scratchpad": 0x4,
    "interrupt_status": 0x2C,
    "pim_status": 0x40,
    "pim_present_intr_mask": 0x44,
}

dom_base = [
 0xFFFFFFFF, # Padding
 0x40000,
 0x48000,
 0x50000,
 0x58000,
 0x60000,
 0x68000,
 0x70000,
 0x78000,
]


dom = {
  "revision": 0x0,
  "intr_status": 0x2C,
  "qsfp_present": 0x48,
  "qsfp_present_intr": 0x50,
  "qsfp_present_intr_mask": 0x58,
  "qsfp_intr": 0x60,
  "qsfp_intr_mask": 0x68,
  "qsfp_reset": 0x70,
  "qsfp_lp_mode": 0x78,
  "device_power_bad_status": 0x90,
  "dom_control_config": 0x410,
  "dom_global_status": 0x414,
  "dom_data": 0x4000,
  

  "mdio": {
    "config":  0x0200,
    "command": 0x0204,
    "write":   0x0208,
    "read":    0x020C,
    "status":  0x0210,
    "intr_mask": 0x0214,
    "source_sel": 0x0218,
  }, # mdio
}

mdio_read_cmd = 0x1
mdio_write_cmd = 0x0
mdio_device_type = 0x1F


#fbfpgaio=cdll.LoadLibrary('./fbfpgaio.so')

def init_resources():
  #print "init_resources"
  fbfpgaio.hw_init()
  return

def release_resources():
  #print "release_resources"
  fbfpgaio.hw_release()
  return

def fpga_io(offset, data=None):
  if data is None:
    return fbfpgaio.hw_io(offset)
  else:
    fbfpgaio.hw_io(offset, data)
    return

def pim_io(pim, offset, data=None):
  global dom_base
  target_offset = dom_base[pim]+offset
  if data is None:
    retval = fpga_io(target_offset)
    #print ("0x%04X" % retval) # idebug
    return retval
  else:
    retval = fpga_io(target_offset, data)
    return retval


def show_pim_present():
  pim_status = fpga_io(iob["pim_status"])
  
  header =     "PIM # "
  status_str = "      "
  for shift in range(0,8):
    status = pim_status & (0x10000 << shift)   #[23:16] from pim_0 to pim_7
    header += " %d " % (shift+1)
    if status:
      status_str += (" | ")
    else:
      status_str += (" X ")
  print(header)
  print(status_str)

def show_qsfp_present_status(pim_num):
     status = fpga_io(dom_base[pim_num]+dom["qsfp_present"])
     interrupt = fpga_io(dom_base[pim_num]+dom["qsfp_present_intr"])
     mask = fpga_io(dom_base[pim_num]+dom["qsfp_present_intr_mask"])

     print
     print("    (0x48)      (0x50)      (0x58)")
     print("    0x%08X  0x%08X  0x%08X" %(status, interrupt, mask))
     print("    Status      Interrupt   Mask")
     for row in range(8):
         output_str = str()
         status_left = bool(status & (0x1 << row*2))
         status_right = bool(status & (0x2 << row*2))
         interrupt_left = bool(interrupt & (0x1 << row*2))
         interrupt_right = bool(interrupt & (0x2 << row*2))
         mask_left = bool(mask & (0x1 << row*2))
         mask_right = bool(mask & (0x2 << row*2))
         print("%2d:  %d  %d         %d  %d       %d %d" % \
                 (row*2+1, status_left, status_right, \
                        interrupt_left, interrupt_right, \
                        mask_left, mask_right))
         print



#pim_index start from 0 to 7
#port_index start from 0 to 127. Each 16-port is to one pim card.
class PimUtil(object):

    PORT_START = 0
    PORT_END = 127

    def __init__(self):
        self.value=1        

    def __del__(self):
        self.value=0
        
    def init_pim_fpga(self):
        init_resources()    
    
    def release_pim_fpga(self):
        release_resources()

    def get_pim_by_port(self, port_num):
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False
        pim_num=port_num/16
        return True, pim_num+1
    
    def get_onepimport_by_port(self, port_num):
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False
        if port_num < 16:
            return True, port_num
        else:
            return True, port_num%16   

    def get_pim_presence(self, pim_num):
        if pim_num <0 or pim_num > 7:
            return 0
        pim_status = fpga_io(iob["pim_status"])
        status = pim_status & (0x10000 << pim_num)
        if status:
            return 1 #present
        else:
            return 0 #not present

    #return code=0:100G. return code=1:400G
    def get_pim_board_id(self, pim_num):
        if pim_num <0 or pim_num > 7:
            return False
        board_id = fpga_io(dom_base[pim_num+1]+dom["revision"])
        if board_id==0x0:
            return 0
        else:
            return 1


    def get_pim_status(self, pim_num):
        if pim_num <0 or pim_num > 7:
            return 0xFF
        power_status =0
        #device_power_bad_status
        status=fpga_io(dom_base[pim_num+1]+dom["device_power_bad_status"])
        
        for x in range(0, 5):
            if status & ( (x+1) << (4*x) ) :
                power_status = power_status | (0x1 << x)
        
        if ( status & 0x1000000):
            power_status=power_status | (0x1 << 5)
        if ( status & 0x2000000):
            power_status=power_status | (0x1 << 6)
        if ( status & 0x8000000):
            power_status=power_status | (0x1 << 7)
        if ( status & 0x10000000):
            power_status=power_status | (0x1 << 8)
        if ( status & 0x40000000):
            power_status=power_status | (0x1 << 9)
        if ( status & 0x80000000):
            power_status=power_status | (0x1 << 10)

        return power_status
    #path=0:MDIO path is set on TH3. path=1:MDIO path is set on FPGA.
    def set_pim_mdio_source_sel(self, pim_num, path):
        if pim_num <0 or pim_num > 7:
            return False
        status= pim_io(pim_num+1, dom["mdio"]["source_sel"])
        
        if path==1:
            status = status | 0x2
        else:
            status = status & 0xfffffffd
        
        pim_io(pim_num+1, dom["mdio"]["source_sel"], status)
        return True
    #retrun code=0, path is TH3. retrun code=1, path is FPGA
    def get_pim_mdio_source_sel(sefl, pim_num):
        if pim_num <0 or pim_num > 7:
            return False
        path= pim_io(pim_num+1, dom["mdio"]["source_sel"])
        path = path & 0x2
        if path:
            return 1
        else:
            return 0
    
    #This api will set mdio path to MAC side.(At default, mdio path is set to FPGA side).
    def pim_init(self, pim_num):
        if pim_num <0 or pim_num > 7:
            return False
        status=self.set_pim_mdio_source_sel(pim_num+1, 0)
        #put init phy cmd here
    
    
    #return code="pim_dict[pim_num]='1' ":insert evt. return code="pim_dict[pim_num]='0' ":remove evt
    def get_pim_change_event(self, timeout=0):
        start_time = time.time()
        pim_dict = {}
        forever = False

        if timeout == 0:
            forever = True
        elif timeout > 0:
            timeout = timeout / float(1000) # Convert to secs
        else:
            print "get_transceiver_change_event:Invalid timeout value", timeout
            return False, {}

        end_time = start_time + timeout
        if start_time > end_time:
            print 'get_transceiver_change_event:' \
                       'time wrap / invalid timeout value', timeout

            return False, {} # Time wrap or possibly incorrect timeout

        pim_mask_status = fpga_io(iob["pim_present_intr_mask"], 0xffff00000)
        
        while timeout >= 0: 
            new_pim_status=0           
            pim_status = fpga_io(iob["pim_status"])
            present_status= pim_status & 0xff0000
            change_status=pim_status & 0xff 
            interrupt_status = fpga_io(iob["interrupt_status"])
            
            for pim_num in range(0,8):
                if change_status & (0x1 << pim_num) :
                     status = present_status & (0x10000 << pim_num)
                     new_pim_status = new_pim_status | (0x1 << pim_num) #prepare to W1C to clear                     
                     if  status:
                        pim_dict[pim_num]='1'
                     else:
                        pim_dict[pim_num]='0'

            if change_status:
                new_pim_status = pim_status | new_pim_status #Write one to clear interrupt bit
                fpga_io(iob["pim_status"], new_pim_status)
                return True, pim_dict
            if forever:
                time.sleep(1)
            else:
                timeout = end_time - time.time()
                if timeout >= 1:
                    time.sleep(1) # We poll at 1 second granularity
                else:
                    if timeout > 0:
                        time.sleep(timeout)
                    return True, {}
        print "get_evt_change_event: Should not reach here."
        return False, {}


    def get_qsfp_presence(self, port_num):
         #xlate port to get pim_num
         status, pim_num=self.get_pim_by_port(port_num)

         if status==0:
            return False
         else:
            present = fpga_io(dom_base[pim_num]+dom["qsfp_present"])
         status, shift = self.get_onepimport_by_port(port_num)
         if status==0:
             return False
         else:
             if bool(present & (0x1 << shift)):
                 return 1 #present
             else:
                 return 0 #not present

    #return code: low_power(1) or high_power(0)
    def get_low_power_mode(self, port_num):
        status, pim_num=self.get_pim_by_port(port_num)
        
        if status==0:
            return False
        else:
            lp_mode = fpga_io(dom_base[pim_num]+dom["qsfp_lp_mode"])
        
        status, shift=self.get_onepimport_by_port(port_num)
        if status==0:
            return False
        else:
            if (lp_mode & (0x1 << shift)):
                return 1 #low
            else:
                return 0 #high

    #lpmode=1 to hold QSFP in low power mode. lpmode=0 to release QSFP from low power mode.
    def set_low_power_mode(self, port_num, mode):
        status, pim_num=self.get_pim_by_port(port_num)        
        if status==0:
            return False        
        val = fpga_io(dom_base[pim_num]+dom["qsfp_lp_mode"])        
        status, shift=self.get_onepimport_by_port(port_num)        
        if status==0:
            return False
        else:
            if mode==0:
                new_val = val & (~(0x1 << shift))
            else:
                new_val=val|(0x1 << shift)
        status=fpga_io(dom_base[pim_num]+dom["qsfp_lp_mode"], new_val)
        return status
    
    #port_dict[idx]=1 means get interrupt(change evt), port_dict[idx]=0 means no get interrupt
    def get_qsfp_interrupt(self):
        port_dict={}
        #show_qsfp_present_status(1)
        for pim_num in range(0, 8):
            fpga_io(dom_base[pim_num+1]+dom["qsfp_present_intr_mask"], 0xffff0000)
            fpga_io(dom_base[pim_num+1]+dom["qsfp_intr_mask"], 0xffff0000)
        for pim_num in range(0, 8):            
            clear_bit=0            
            qsfp_present_intr_status = fpga_io(dom_base[pim_num+1]+dom["qsfp_present_intr"])
            interrupt_status = qsfp_present_intr_status & 0xffff
            #time.sleep(2)            
            if interrupt_status:
                for idx in range (0,16):
                    port_idx=idx + (pim_num*16)
                    if interrupt_status & (0x1<<idx):
                        port_dict[port_idx]=1
                        clear_bit=clear_bit | (0x1<<idx)  #W1C to clear
                    else:
                        port_dict[port_idx]=0
                
                #W1C to clear
                fpga_io(dom_base[pim_num+1]+dom["qsfp_present_intr"], qsfp_present_intr_status | clear_bit) 
                
        return port_dict
        
    def reset(self, port_num):
        status, pim=self.get_pim_by_port(port_num)
        if status==0:
            return False
        
        val=fpga_io(dom_base[pim]+dom["qsfp_reset"])        
        status, shift=self.get_onepimport_by_port(port_num)
        if status==0:
            return False
        else:               
            val = val & (~(0x1 << shift))
        fpga_io(dom_base[pim]+dom["qsfp_reset"], val)
        return True

def main(argv):
    init_resources()    
    pim=PimUtil()
    print "Test Board ID"
    for x in range(0,8):
        val=pim.get_pim_board_id(x)
        print "pim=%d"%x
        if val==0:
            print "100G board"
        else:
            print "400G board"
    
    print "Test pim presence"
    for x in range(0,8):
        pres=pim.get_pim_presence(x)
        print "pim=%d, presence=%d"%(x, pres)   
        
    print "Test pim status"
    for x in range(0,8):
        power_status=pim.get_pim_status(x)
        print "pim=%d power_status=0x%x"%(x, power_status)
    
    release_resources()

if __name__ == '__main__':
    main(sys.argv[1:])
