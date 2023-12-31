<?PHP
/*
Copyright (c) 2022, Hans kim

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

/*
CREATE TABLE `gate_control` (
  `pk` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `regdate` datetime DEFAULT NULL,
  `timestamp` double DEFAULT NULL,
  `id` varchar(127) default '',
  `eventinfo` text DEFAULT NULL,
  `snapshot` mediumblob DEFAULT NULL,
  `flag` enum('y','n') DEFAULT 'n',
  `user_agent` text DEFAULT NULL,
  PRIMARY KEY (`pk`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 |

CREATE TABLE `gate_users` (
  `pk` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `regdate` datetime DEFAULT NULL,
  `id` varchar(127),
  `api_key` varchar(127),
  `date_from` date DEFAULT '0000-00-00',
  `hour_from` int(3) default 0,
  `date_to` date DEFAULT '0000-00-00',
  `hour_to` int(3) default 0,
  `flag` enum('y','n') DEFAULT 'n',
  PRIMARY KEY (`pk`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 |
*/

/* on centos 8, file_get_contents
setsebool -P httpd_can_network_connect 1
*/
/* 
hanskimvz:	a302c4f450ce16068ccad07139453953
vivasejin:	fb16fea114c5788ab752f0dbca224c5c
yhchoi:		22e1ceca8cca9d183842267f15ff2b35
jay: 		baba327d241746ee0829e7e88117d4d5
*/

// print "<pre>"; print_r ($_SERVER); print "</pre>"; exit();

$fname = "setting.json";
// chcon -t httpd_sys_rw_content_t setting.json 
$SETTING = json_decode(file_get_contents($fname), True) or die("cannot open file");
// print "<pre>"; print_r($SETTING); print "</pre>";

$connect = @mysqli_connect($SETTING['MYSQL']['host'], $SETTING['MYSQL']['user'], $SETTING['MYSQL']['pass'], $SETTING['MYSQL']['db_name']);
if(!$connect) {
	echo "DB  Select Error Custom";
	exit();
}

function request($url, $method='GET', $body='', $https_user='', $https_password='') {
    $opts = array('http' =>
        array(
            'method'  => $method,
            'header'  => "Content-Type: text/xml\r\n".
            "Authorization: Basic ".base64_encode("$https_user:$https_password")."\r\n",
            'content' => $body,
            'timeout' => 60
        )
    );

    $context  = stream_context_create($opts);
    $result = file_get_contents($url, false, $context, -1, 40000);
}
function getSnapshot($num = 0) {
	global $SETTING;
    $DEV = $SETTING['CAMERAS'][$num];
	$url = sprintf("http://%s:%s@%s/%s", $DEV['userid'], $DEV['userpw'], $DEV['address'],$DEV['snapshot_cgi']);

    // print $url;
	$body = file_get_contents($url);
	$img_b64 = "data:image/jpg;base64,".base64_encode($body);
	return $img_b64;
}

function putDO($secs = 0){
	global $SETTING;
    $DEV = $SETTING['CAMERAS'][0];
    if ($secs == 0) {
        $cgi = $DEV['DO_cgi']['on'];
    }
    else if ($secs == -1) {
        $cgi = $DEV['DO_cgi']['off'];
    }
    else {
        $cgi = $DEV['DO_cgi']['trig'].$secs;
    }
    $url = sprintf("http://%s:%s@%s/%s", $DEV['userid'],$DEV['userpw'],$DEV['address'], $cgi);
	// print $url;
	$body = file_get_contents($url);
	if (substr($body, 0,4) == "#200") {
		return True;
    }
}

function validDatetime($date_from, $date_to, $hour_from, $hour_to){
	$ts_now  = time() + 3600*9;
	$ts_from = strtotime($date_from.' 00:00:00');
	$ts_to  = strtotime($date_to.' 24:00:00');
	$hour = date('H', $ts_now);

	if ($ts_now < $ts_from || $ts_now > $ts_to) {
		print ("Not in date <br />");
		return False;
	}
	if ($hour_from + $hour_to !=0 ) {
		if ($hour < $hour_from || $hour > ($hour_to-1)) {
			print ("Not in hour <br />");
			return False;
		}
	}
	return True;

}

function getUser($api_key) {
	global $SETTING;
	global $connect;
	$sq = "select * from ".$SETTING['MYSQL']['user_table']." where api_key = '".$api_key."' ";
	$rs = mysqli_query($connect, $sq);
	if (!$rs->num_rows) {
		return False;
	}
	$assoc = mysqli_fetch_assoc($rs);
	return [$assoc['id'], $assoc['name']];
}


function logDB($cam_no=0) {
	global $SETTING;
	global $connect;
    $MYSQL = $SETTING['MYSQL'];

	$timestamp = microtime(true) + 3600*9;
	$regdate= date("Y-m-d H:i:s", floor($timestamp));
	$event_info = '{ "ip": "'.$_SERVER['REMOTE_ADDR'].'", "mode": "'.$_POST['mode'].', "api_key": "'.$_POST['api_key'].'"}';
	$user_id = getUser($_POST['api_key'])[0];
	$snapshot = getSnapshot($cam_no);
	
	$sq = "select pk from ".$MYSQL['db_name'].".".$MYSQL['log_table']." where timestamp < ".($timestamp-2592000)." order by timestamp asc limit 1";
	$rs = mysqli_query($connect, $sq);
	if ($rs->num_rows){
		$pk = mysqli_fetch_row($rs)[0];
		$sq = "update ".$MYSQL['db_name'].".".$MYSQL['log_table']." set  regdate='".$regdate."', timestamp=".$timestamp.", id='".$user_id."', eventinfo='".$event_info."', user_agent='".addslashes($_SERVER['HTTP_USER_AGENT'])."', snapshot='".addslashes($snapshot)."', flag='n'  where pk=".$pk;
	}
	else {
		$sq = "insert into ".$MYSQL['db_name'].".".$MYSQL['log_table']."(regdate, timestamp, id, eventinfo, user_agent, snapshot, flag)  values('".$regdate."', ".$timestamp.", '".$user_id."', '".$event_info."', '".addslashes($_SERVER['HTTP_USER_AGENT'])."', '".addslashes($snapshot)."', 'n')";
	}
	// print $sq;
	$rs = mysqli_query($connect, $sq);
	
	if($rs) {
		print "log OK";
		return True;
	}
	print "Fail to log";
	return False;
}
function listLog() {
	global $SETTING;
	global $connect;
    $MYSQL = $SETTING['MYSQL'];
    if (!$_GET['page']) {
        $_GET['page'] = 1;
    }
    if (!$_GET['offset']) {
        $_GET['offset'] = 20;
    }

	$sq = "select * from ".$MYSQL['db_name'].".".$MYSQL['log_table']." order by timestamp desc limit ".(($_GET['page']-1)*$_GET['offset']).", ".$_GET['offset']." ";
    // print $sq;
	$rs = mysqli_query($connect, $sq);
	while ($assoc = mysqli_fetch_assoc($rs)){
		$table_body .= '<tr>
			<td>'.$assoc['pk'].'</td>
			<td>'.$assoc['regdate'].'</td>
			<td>'.$assoc['id'].'</td>
			<td>'.$assoc['eventinfo'].'</td>
			<td><img id="img['.$assoc['pk'].']" src = "'.$assoc['snapshot'].'" width="100px"></img></td>
            <td>'.$assoc['user_agent'].'</td>
            
		
		</tr>';
	}
	$table_body = '<table><tr><td>pk</td><td>regdate</td><td>id</td><td>event info</td><td>snapshot</td><td>user_agent</td></tr>'.$table_body.'</table>';
	return $table_body;

}

$HEAD = <<<EOBLOCK
	<head>
		<meta charset="utf-8">
		<meta http-equiv="X-UA-Compatible" content="IE=edge">
		<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
		<meta name="description" content="Responsive Bootstrap 4 Admin &amp; Dashboard Template">
		<meta name="author" content="Bootlab">
		<title id='title'>Admin Tools</title>
        <style type="text/css">
            body {background-color: #fff; color: #222; font-family: sans-serif;}
            /* pre {margin: 0; font-family: monospace;}
            a:link {color: #009; text-decoration: none; background-color: #fff;}
            a:hover {text-decoration: underline;} */
            table {border-collapse: collapse; border: 0; width: 100%; box-shadow: 1px 2px 3px #eee;}
            .center {text-align: center;}
            .center table {margin: 1em auto; text-align: left;}
            .center th {text-align: center !important;}
            td, th {border: 1px solid #aaa; font-size: 75%; vertical-align: baseline; padding: 4px 5px;}
            h1 {font-size: 150%;}
            h2 {font-size: 125%;}
            .p {text-align: left;}
            .e {background-color: #ccf; width: 300px; font-weight: bold;}
            .h {background-color: #99c; font-weight: bold;}
            .v {background-color: #ddd; max-width: 300px; overflow-x: auto; word-wrap: break-word;}
            .v i {color: #999;}
            img {float: right; border: 0;}
            hr {width: 934px; background-color: #ccc; border: 0; height: 1px;}
            bigPictureWrapper {
                position: absolute;
                display: none;
                justify-content: center;
                align-items: center;
                top:0%;
                width:100%;
                height:100%;
                background-color: gray; 
                z-index: 100;
                background:rgba(255,255,255,0.5);
            }
            .bigPicture {
                position: relative;
                display:flex;
                justify-content: center;
                align-items: center;
            }
            
            .bigPicture img {
                width:100%;
            }            
        </style>
	</head>

EOBLOCK;

############### main #################
if (!$_GET['mode'] && !$_POST['mode']) {
    $_GET['mode'] = 'ready';
}
// print_r($_GET);

if ($_GET['mode'] == 'ready') {
	if (strpos($_SERVER['HTTP_USER_AGENT'], "Windows") > 0 && $_SERVER['HTTP_HOST'] != '192.168.1.250') {
		print "Cannot use on windows<br / >";
		exit();
	}
	list($user_id, $user_name) = getUser($_GET['api_key']);
	if($user_id) {
		$btn_open = '<input type="button" name="open_button" value="OPEN" style="width:300px; height:200px; font-size: 60px !important;" onClick="open_door()" />';
	}
	print '<body>
		<input type="hidden" id="mode" value="'.$_GET['mode'].'">
		<table align="center">	
			<tr><td align="center">'.$user_id.':'.$user_name.'</td></tr>
			<tr><td align="center">'.$btn_open.'</td></tr>
			<tr><td id="result" align="center" style="color:#FF0000;"></td></tr>
			<tr><td align="center"><input type="button" name="refresh_button" value="Refresh" style="width:100px; height:50px; font-size: 20px !important;" onClick="location.reload()"></td></tr>
		</table>
        <!--iframe src = "./snapshot.php" frameborder=0 width="100%" height="100%"></iframe-->
		<img id="snapshot" src = "'.getSnapshot().'" width="100%"></img>
	</body>';

}

if ($_GET['mode'] == 'list_users') {
	$sq = "select * from ".$SETTING['MYSQL']['user_table']." order by regdate asc";
	print $sq;
	$rs = mysqli_query($connect, $sq);
	$table_body = '';
	while($assoc=mysqli_fetch_assoc($rs)){
		// $assoc['id'] = '<span onClick="view_user('.$assoc['pk'].')">'.$assoc['id'].'</span>';
		if ($assoc['api_key'] != md5($assoc['id'])) {
			$assoc['api_key'] = '<font color="#FF0000">'.$assoc['api_key'].'</font>';
		}
		$table_body .= '<tr id="user_info['.$assoc['pk'].']">
			<td><input type="text" id="id['.$assoc['pk'].']" value="'.$assoc['id'].'" size="12"></td>
			<td><input type="text" id="name['.$assoc['pk'].']" value="'.$assoc['name'].'" size="5"></td>
			<td><input type="text" id="plate['.$assoc['pk'].']" value="'.$assoc['plate'].'" size="10"></td>
			<td>'.$assoc['regdate'].'</td>
			<td><a href="http://124.61.244.239:8000/gateControl/?api_key='.$assoc['api_key'].'">'.$assoc['api_key'].'</a></td>
			<td><input type="text" id="date_from['.$assoc['pk'].']" value="'.$assoc['date_from'].'" size="10"></td>
			<td><input type="text" id="hour_from['.$assoc['pk'].']" value="'.$assoc['hour_from'].'" size="5"></td>
			<td><input type="text" id="date_to['.$assoc['pk'].']" value="'.$assoc['date_to'].'" size="10"></td>
			<td><input type="text" id="hour_to['.$assoc['pk'].']" value="'.$assoc['hour_to'].'" size="5"></td>
			<td><input type="checkbox" id="flag['.$assoc['pk'].']" value="y" '.($assoc['flag']=='y'? "checked":"").'></td>
			<td><input type="button" value="Confirm" onClick="changeUserInfo('.$assoc['pk'].')"></td>
			<td id="rs['.$assoc['pk'].']"></td>
		</tr>';
	}
	$table_body .= '<tr id="user_info[0]">
		<td><input type="text" id="id[0]" value="" size="12"></td>
		<td><input type="text" id="name[0]" value="" size="5"></td>
		<td><input type="text" id="plate[0]" value="" size="10"></td>
		<td></td>
		<td></td>
		<td><input type="text" id="date_from[0]" value="0000-00-00" size="10"></td>
		<td><input type="text" id="hour_from[0]" value="0" size="5"></td>
		<td><input type="text" id="date_to[0]" value="0000-00-00" size="10"></td>
		<td><input type="text" id="hour_to[0]" value="0" size="5"></td>
		<td><input type="checkbox" id="flag[0]" value="y"></td>
		<td><input type="button" value="Add" onClick="changeUserInfo(0)"></td>
		<td id="rs[0]"></td>
	</tr>';

	$table_body = '<table><tr>
		<th>id</th>
		<td>name</td>
		<td>plate</td>
		<th>regdate</th>
		<th>api_key</th>
		<th>date_from</th>
		<th>hour_from</th>
		<th>date_to</th>
		<th>hour_to</th>
		<th>flag</th>
		</tr>'.$table_body.'</table>';
	print '<html lang="en">'.$HEAD.$table_body.'</html>';
}
else if ($_POST['mode'] == 'modify_user') {
	$_POST['flag']  = $_POST['flag'] == 'true' ? 'y' :'n';
	$_POST['id'] = trim($_POST['id']);
	if(!$_POST['id']) {
		print "ID fail";
		exit();
	}			

	if ($_POST['pk']) {
		$sq = "update ".$SETTING['MYSQL']['user_table']." set
		 id='".$_POST['id']."', 
		 name='".addslashes(trim($_POST['name']))."', 
		 plate='".addslashes(trim($_POST['plate']))."', 
		 date_from='".$_POST['date_from']."', 
		 hour_from='".$_POST['hour_from']."', 
		 date_to='".$_POST['date_to']."', 
		 hour_to='".$_POST['hour_to']."', 
		 flag='".$_POST['flag']."', 
		 api_key= '".md5($_POST['id'])."' where pk=".$_POST['pk'];
	}
	else {
		$sq = "insert into gate_users(regdate, id, name, plate, api_key, date_from, hour_from, date_to, hour_to, flag) values(now(), '".$_POST['id']."','".addslashes(trim($_POST['name']))."', '".addslashes(trim($_POST['plate']))."','".md5($_POST['id'])."', '".$_POST['date_from']."','".$_POST['hour_from']."','".$_POST['date_to']."','".$_POST['hour_to']."', '".$_POST['flag']."') ";
	}
	// print $sq;
	$rs = mysqli_query($connect, $sq);
	if ($rs){
		print "OK";
	}
	else {
		print "FAIL";
	}
	exit();
}


else if ($_GET['mode'] == 'list_log') {
    print $HEAD;
    print '<div class="bigPictureWrapper">
        <div class="bigPicture"></div>
    </div>';
    print '<div>'.listLog().'</div>';
}


else if ($_POST['mode'] == 'snapshot'){
	print getSnapshot($_POST['cam_no']);
	exit();
}

else if ($_POST['mode'] == 'open') {
	global $SETTING;
	global $connect;
	
	$user_id = getUser($_POST['api_key'])[0];
	if (!$user_id) {
		echo "api key not match";
		exit();
	}
	$sq = "select * from ".$SETTING['MYSQL']['user_table']." where id='".$user_id."' ";
	$rs = mysqli_query($connect, $sq);
	$assoc = mysqli_fetch_assoc($rs);

	if ($assoc['flag'] == 'n') {
		echo "Not valid auth, contact admin <br />";
		exit();
	}

	if (validDatetime($assoc['date_from'], $assoc['date_to'], $assoc['hour_from'], $assoc['hour_to'])) {
		$ret = putDO(1);
	
		if ($ret) {
			echo "opened OK<br />";
		}
		else {
			echo "Fail to open<br />";
		}
	}
	else {
		echo "Not valid datetime, contact admin <br />";
		exit();
	}
	
	logDB();
	exit();
}

// open from external camera
else if ($_GET['mode'] == 'exit') {
	$user_id = getUser($_GET['api_key'])[0];

	if ($user_id == 'vivasejin'){
		putDO(1);
		echo "opened";
		logDB(1);
	}
	else {
		echo "check api_key";
	}
	exit();

}

// $img_url = sprintf("http://%s:%s@%s/nvc-cgi/operator/snapshot.fcgi", $SETTING['CAMERA']['userid'], $SETTING['CAMERA']['userpw'], $SETTING['CAMERA']['address']);
// echo $img_url;
// if (md5("vivasejin") == $_GET['api_key']) {



?>

<script type="text/javascript" src="/js/jquery.min.js"></script>
<script>

function snapshot(n=0){
	url = "<?=$_SERVER['DOCUMENT_URI']?>";
	formData = {
		"api_key": "<?=$_GET['api_key']?>",
		"mode": "snapshot",
		"cam_no": n
	}	
	let posting = $.post(url,formData);
	posting.done(function(data) {
		// console.log(data);
		document.getElementById("snapshot").src = data;
	});	
}
function refresh(){
	document.getElementById("result").innerHTML = '';
	snapshot();
}

function open_door(){
	url = "<?=$_SERVER['DOCUMENT_URI']?>";
	formData = {
		"api_key": "<?=$_GET['api_key']?>",
		"mode": "open"
	}	
	let posting = $.post(url,formData);
	posting.done(function(data) {
		console.log(data);
		document.getElementById("result").innerHTML = data;
		snapshot();
	});	

}

function changeUserInfo(pk) {
	url = "<?=$_SERVER['DOCUMENT_URI']?>";
	formData = {
		"api_key": "<?=$_GET['api_key']?>",
		"pk": pk,
		"mode": "modify_user",
		"id": document.getElementById("id["+pk+"]").value,
		"name": document.getElementById("name["+pk+"]").value,
		"plate": document.getElementById("plate["+pk+"]").value,
		"date_from": document.getElementById("date_from["+pk+"]").value,
		"hour_from": document.getElementById("hour_from["+pk+"]").value,
		"date_to": document.getElementById("date_to["+pk+"]").value,
		"hour_to": document.getElementById("hour_to["+pk+"]").value,
		"flag": document.getElementById("flag["+pk+"]").checked
	}
	if (pk==0) {
		formData['id'] = document.getElementById("id["+pk+"]").value;
	}
	document.getElementById("rs["+pk+"]").innerHTML="";
	let posting = $.post(url, formData);
	posting.done(function(data) {
		console.log(data);
		document.getElementById("rs["+pk+"]").innerHTML=data;
	});	
}

$(document).ready(function (e){
	console.log(e)
	$(document).on("click","img",function(){
		// var wow = window.open("", "img",);
		// wow.document.write('<body leftmargin=0 topmargin=0 marginwidth=0 marginheight=0><div class="bigPictureWrapper"><div class="bigPicture"></div></div></body>');

		var path = $(this).attr('src');
		showImage(path);
	});//end click event
	
	function showImage(fileCallPath){
		$(".bigPictureWrapper").css("display","flex").show();
		
		$(".bigPicture")
		.html("<img src='"+fileCallPath+"' >")
		.animate({width:'100%', height: '100%'}, 1000);
		
		}//end fileCallPath
		
	$(".bigPictureWrapper").on("click", function(e){
		$(".bigPicture").animate({width:'0%', height: '0%'}, 1000);
		setTimeout(function(){
			$('.bigPictureWrapper').hide();
		}, 1000);
		});//end bigWrapperClick event
});

if (document.getElementById('mode').value  == 'ready') {
	setInterval(() => {
	    snapshot();
	}, 3000);
}
</script>

